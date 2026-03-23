"""
Rutas API para gestión de proyectos.
Todo gira alrededor del Project: scraping, configs, ejecuciones.
"""
import os
import threading
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request, send_file, current_app
from app.automation.timing import DEFAULT_EXECUTION_PROFILE, resolve_execution_profile
from app.database.connection import db
from app.database.models import Project, ProjectConfig, Execution

project_bp = Blueprint("project", __name__)
MIN_PERFILES = 3
MAX_PERFILES = 4
MIN_TENDENCIAS = 3
MAX_TENDENCIAS = 4


def _validar_configuracion(perfiles, reglas, tendencias):
    if len(perfiles) < MIN_PERFILES or len(perfiles) > MAX_PERFILES:
        return jsonify({"error": "Se requieren entre 3 y 4 perfiles"}), 400
    if len(tendencias) < MIN_TENDENCIAS or len(tendencias) > MAX_TENDENCIAS:
        return jsonify({"error": "Se requieren entre 3 y 4 tendencias"}), 400
    if len(reglas) < 1:
        return jsonify({"error": "Se requiere mínimo 1 regla"}), 400
    return None


def _guardar_configuracion_proyecto(
    project,
    *,
    nombre,
    perfiles,
    reglas,
    tendencias,
    ai_provider_used="",
    replace_existing=False,
    replace_config_id=None,
):
    existing_config = None
    if replace_existing:
        if replace_config_id:
            existing_config = ProjectConfig.query.filter_by(
                id=replace_config_id,
                project_id=project.id,
            ).first()
        if not existing_config:
            existing_config = project.get_active_config()

    ProjectConfig.query.filter_by(project_id=project.id, is_active=True).update({"is_active": False})

    if existing_config:
        existing_config.nombre = nombre or existing_config.nombre or "Importado"
        existing_config.perfiles = perfiles
        existing_config.reglas_dependencia = reglas
        existing_config.tendencias_escalas = tendencias
        existing_config.ai_provider_used = ai_provider_used
        existing_config.is_active = True
        project.status = "configurado"
        db.session.commit()
        return existing_config, False

    config = ProjectConfig(
        project_id=project.id,
        nombre=nombre,
        perfiles=perfiles,
        reglas_dependencia=reglas,
        tendencias_escalas=tendencias,
        ai_provider_used=ai_provider_used,
        is_active=True,
    )
    db.session.add(config)
    project.status = "configurado"
    db.session.commit()
    return config, True


# ═══════════════ CRUD PROYECTOS ═══════════════

@project_bp.route("/projects", methods=["POST"])
def crear_proyecto():
    """Crea un nuevo proyecto."""
    data = request.json or {}
    nombre = data.get("nombre", "").strip()
    url = data.get("url", "").strip()

    if not nombre:
        return jsonify({"error": "Nombre requerido"}), 400
    if not url:
        return jsonify({"error": "URL requerida"}), 400

    project = Project(nombre=nombre, descripcion=data.get("descripcion", ""), url=url)
    db.session.add(project)
    db.session.commit()

    return jsonify(project.to_dict()), 201


@project_bp.route("/projects", methods=["GET"])
def listar_proyectos():
    """Lista todos los proyectos."""
    projects = Project.query.order_by(Project.created_at.desc()).all()
    return jsonify([p.to_dict_simple() for p in projects])


@project_bp.route("/projects/<int:project_id>", methods=["GET"])
def obtener_proyecto(project_id):
    """Obtiene detalle completo de un proyecto."""
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Proyecto no encontrado"}), 404

    result = project.to_dict()
    result["estructura"] = project.estructura
    return jsonify(result)


@project_bp.route("/projects/<int:project_id>", methods=["PUT"])
def actualizar_proyecto(project_id):
    """Actualiza nombre/descripcion/url de un proyecto."""
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Proyecto no encontrado"}), 404

    data = request.json or {}
    if "nombre" in data:
        project.nombre = data["nombre"]
    if "descripcion" in data:
        project.descripcion = data["descripcion"]
    if "url" in data:
        project.url = data["url"]
        # Si cambia la URL, resetear estructura
        project.estructura = None
        project.status = "nuevo"

    db.session.commit()
    return jsonify(project.to_dict())


@project_bp.route("/projects/<int:project_id>", methods=["DELETE"])
def eliminar_proyecto(project_id):
    """Elimina un proyecto y todo su contenido."""
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Proyecto no encontrado"}), 404

    # Verificar que no haya ejecuciones activas
    ejecutando = Execution.query.filter_by(project_id=project_id, status="ejecutando").first()
    if ejecutando:
        return jsonify({"error": "No se puede eliminar, hay una ejecución activa"}), 400

    db.session.delete(project)
    db.session.commit()
    return jsonify({"mensaje": "Proyecto eliminado"})


# ═══════════════ SCRAPING ═══════════════

@project_bp.route("/projects/<int:project_id>/scrape", methods=["POST"])
def scrape_proyecto(project_id):
    """Scrapea el formulario del proyecto."""
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Proyecto no encontrado"}), 404

    data = request.json or {}

    try:
        ai_service = current_app.config.get("AI_SERVICE")
        from app.scraping import get_scraper
        scraper = get_scraper(project.url, ai_service)
        headless = data.get("headless", True)
        estructura = scraper.scrape(project.url, headless=headless)

        if estructura.get("requiere_login"):
            return jsonify({"error": "Formulario requiere login. Solo se soportan formularios públicos."}), 400

        # Actualizar proyecto
        project.estructura = {"paginas": estructura.get("paginas", [])}
        project.plataforma = estructura.get("plataforma", "google_forms")
        project.total_preguntas = estructura.get("total_preguntas", 0)
        project.requiere_login = False
        project.status = "scrapeado"

        if estructura.get("titulo") and not project.descripcion:
            project.descripcion = estructura.get("descripcion", "")

        db.session.commit()

        result = estructura.copy()
        result["project_id"] = project.id
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ═══════════════ ANÁLISIS IA ═══════════════

@project_bp.route("/projects/<int:project_id>/analyze", methods=["POST"])
def analizar_proyecto(project_id):
    """Analiza el formulario con IA y genera config."""
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Proyecto no encontrado"}), 404
    if not project.estructura:
        return jsonify({"error": "Primero scrapea el formulario"}), 400

    data = request.json or {}
    instrucciones_usuario = data.get("instrucciones", "")

    try:
        ai_service = current_app.config.get("AI_SERVICE")
        if not ai_service:
            return jsonify({"error": "No hay servicio de IA configurado"}), 500

        from app.services.analyzer_service import AnalyzerService
        analyzer = AnalyzerService(ai_service)
        configuracion = analyzer.analyze(project.to_estructura(), instrucciones_extra=instrucciones_usuario)

        return jsonify({
            "preview": True,
            "project_id": project.id,
            "perfiles": configuracion.get("perfiles", []),
            "reglas_dependencia": configuracion.get("reglas_dependencia", []),
            "tendencias_escalas": configuracion.get("tendencias_escalas", []),
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@project_bp.route("/projects/<int:project_id>/apply-config", methods=["POST"])
def aplicar_config_ia(project_id):
    """Aplica una config previamente generada por IA (despues del preview)."""
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Proyecto no encontrado"}), 404

    data = request.json or {}
    perfiles = data.get("perfiles", [])
    reglas = data.get("reglas_dependencia", [])
    tendencias = data.get("tendencias_escalas", [])
    nombre = data.get("nombre", "IA - " + datetime.now().strftime("%d/%m %H:%M"))

    validation_error = _validar_configuracion(perfiles, reglas, tendencias)
    if validation_error:
        return validation_error

    ai_service = current_app.config.get("AI_SERVICE")
    config, created = _guardar_configuracion_proyecto(
        project,
        nombre=nombre,
        perfiles=perfiles,
        reglas=reglas,
        tendencias=tendencias,
        ai_provider_used=ai_service.active_provider_name if ai_service else "",
    )

    result = config.to_dict()
    return jsonify(result), 201 if created else 200


# ═══════════════ CONFIGS ═══════════════

@project_bp.route("/projects/<int:project_id>/configs", methods=["GET"])
def listar_configs(project_id):
    """Lista todas las configs de un proyecto."""
    configs = ProjectConfig.query.filter_by(project_id=project_id).order_by(
        ProjectConfig.is_active.desc(),
        ProjectConfig.updated_at.desc(),
        ProjectConfig.created_at.desc(),
    ).all()
    return jsonify([c.to_dict() for c in configs])


@project_bp.route("/projects/<int:project_id>/configs", methods=["POST"])
def crear_config(project_id):
    """Crea/importa una config para un proyecto."""
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Proyecto no encontrado"}), 404

    data = request.json or {}
    perfiles = data.get("perfiles", [])
    reglas = data.get("reglas_dependencia", [])
    tendencias = data.get("tendencias_escalas", [])

    validation_error = _validar_configuracion(perfiles, reglas, tendencias)
    if validation_error:
        return validation_error

    config, created = _guardar_configuracion_proyecto(
        project,
        nombre=data.get("nombre", "Importado"),
        perfiles=perfiles,
        reglas=reglas,
        tendencias=tendencias,
        ai_provider_used="importado",
        replace_existing=bool(data.get("replace_existing")),
        replace_config_id=data.get("replace_config_id"),
    )

    return jsonify(config.to_dict()), 201 if created else 200


@project_bp.route("/projects/<int:project_id>/configs/<int:config_id>", methods=["PUT"])
def actualizar_config(project_id, config_id):
    """Actualiza una config existente."""
    config = ProjectConfig.query.filter_by(id=config_id, project_id=project_id).first()
    if not config:
        return jsonify({"error": "Config no encontrada"}), 404

    data = request.json or {}

    if "perfiles" in data:
        if len(data["perfiles"]) < MIN_PERFILES or len(data["perfiles"]) > MAX_PERFILES:
            return jsonify({"error": "Se requieren entre 3 y 4 perfiles"}), 400
        config.perfiles = data["perfiles"]
    if "reglas_dependencia" in data:
        if len(data["reglas_dependencia"]) < 1:
            return jsonify({"error": "Se requiere mínimo 1 regla"}), 400
        config.reglas_dependencia = data["reglas_dependencia"]
    if "tendencias_escalas" in data:
        if len(data["tendencias_escalas"]) < MIN_TENDENCIAS or len(data["tendencias_escalas"]) > MAX_TENDENCIAS:
            return jsonify({"error": "Se requieren entre 3 y 4 tendencias"}), 400
        config.tendencias_escalas = data["tendencias_escalas"]
    if "nombre" in data:
        config.nombre = data["nombre"]

    db.session.commit()
    return jsonify(config.to_dict())


@project_bp.route("/projects/<int:project_id>/configs/<int:config_id>/activate", methods=["PUT"])
def activar_config(project_id, config_id):
    """Activa una config (desactiva las demás)."""
    config = ProjectConfig.query.filter_by(id=config_id, project_id=project_id).first()
    if not config:
        return jsonify({"error": "Config no encontrada"}), 404

    ProjectConfig.query.filter_by(project_id=project_id, is_active=True).update({"is_active": False})
    config.is_active = True
    db.session.commit()

    return jsonify({"mensaje": f"Config '{config.nombre}' activada"})


@project_bp.route("/projects/<int:project_id>/configs/<int:config_id>", methods=["DELETE"])
def eliminar_config(project_id, config_id):
    """Elimina una config (no la activa si es la única)."""
    total = ProjectConfig.query.filter_by(project_id=project_id).count()
    if total <= 1:
        return jsonify({"error": "No se puede eliminar la última config"}), 400

    config = ProjectConfig.query.filter_by(id=config_id, project_id=project_id).first()
    if not config:
        return jsonify({"error": "Config no encontrada"}), 404

    was_active = config.is_active
    db.session.delete(config)
    db.session.commit()

    # Si era la activa, activar la más reciente
    if was_active:
        latest = ProjectConfig.query.filter_by(project_id=project_id).order_by(ProjectConfig.created_at.desc()).first()
        if latest:
            latest.is_active = True
            db.session.commit()

    return jsonify({"mensaje": "Config eliminada"})


# ═══════════════ EJECUCIÓN ═══════════════

@project_bp.route("/projects/<int:project_id>/execute", methods=["POST"])
def ejecutar_proyecto(project_id):
    """Inicia ejecución del bot para un proyecto."""
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Proyecto no encontrado"}), 404
    if not project.estructura:
        return jsonify({"error": "Primero scrapea el formulario"}), 400

    config = project.get_active_config()
    if not config:
        return jsonify({"error": "No hay config activa"}), 400

    # Verificar que no haya ejecución activa para ESTE proyecto
    ejecutando = Execution.query.filter_by(project_id=project_id, status="ejecutando").first()
    if ejecutando:
        execution_service = current_app.config.get("EXECUTION_SERVICE")
        if execution_service and not execution_service.is_running(ejecutando.id):
            ejecutando.status = "detenido"
            ejecutando.mensaje = "Detenido (sin hilo activo)"
            db.session.commit()
        else:
            return jsonify({"error": "Este proyecto ya tiene una ejecución activa"}), 400

    data = request.json or {}
    cantidad = data.get("cantidad", 10)
    headless = data.get("headless", True)
    speed_profile = data.get("speed_profile", DEFAULT_EXECUTION_PROFILE)

    if cantidad < 1 or cantidad > 500:
        return jsonify({"error": "Cantidad debe ser entre 1 y 500"}), 400
    try:
        speed_profile = resolve_execution_profile(speed_profile)["id"]
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    execution = Execution(
        project_id=project.id,
        config_id=config.id,
        status="ejecutando",
        mensaje=f"Iniciando {cantidad} encuestas ({speed_profile})...",
        total=cantidad,
        headless=headless,
        started_at=datetime.now(timezone.utc),
    )
    db.session.add(execution)
    db.session.commit()

    execution_service = current_app.config.get("EXECUTION_SERVICE")
    app = current_app._get_current_object()

    hilo = threading.Thread(
        target=execution_service.execute,
        args=(
            app,
            execution.id,
            project.url,
            config.to_configuracion(),
            project.to_estructura(),
            cantidad,
            headless,
            speed_profile,
        ),
    )
    hilo.daemon = True
    hilo.start()

    return jsonify({
        "mensaje": f"Bot iniciado: {cantidad} encuestas ({speed_profile})",
        "execution_id": execution.id,
    })


@project_bp.route("/projects/<int:project_id>/estado", methods=["GET"])
def estado_proyecto(project_id):
    """Estado de la ejecución activa o más reciente del proyecto."""
    execution_id = request.args.get("execution_id", type=int)

    if execution_id:
        execution = Execution.query.filter_by(id=execution_id, project_id=project_id).first()
    else:
        execution = Execution.query.filter_by(project_id=project_id).order_by(Execution.created_at.desc()).first()

    if execution:
        estado = execution.to_estado()
        if execution.status == "ejecutando":
            execution_service = current_app.config.get("EXECUTION_SERVICE")
            if execution_service:
                estado["logs"] = execution_service.get_logs(execution.id)
        return jsonify(estado)

    return jsonify({
        "execution_id": None,
        "project_id": project_id,
        "fase": "idle",
        "mensaje": "Listo",
        "progreso": 0,
        "total": 0,
        "exitosas": 0,
        "fallidas": 0,
        "tiempo_transcurrido": "0s",
        "tiempo_por_encuesta": "0s",
        "excel": None,
        "logs": "",
    })


@project_bp.route("/projects/<int:project_id>/stop", methods=["POST"])
def detener_proyecto(project_id):
    """Detiene la ejecución activa del proyecto."""
    data = request.json or {}
    execution_id = data.get("execution_id")

    if execution_id:
        execution = Execution.query.filter_by(id=execution_id, project_id=project_id).first()
    else:
        execution = Execution.query.filter_by(project_id=project_id, status="ejecutando").first()

    if execution:
        execution_service = current_app.config.get("EXECUTION_SERVICE")
        execution_service.stop(execution.id)
        execution.status = "detenido"
        execution.mensaje = "Detenido por usuario"
        db.session.commit()

    return jsonify({"mensaje": "Detenido"})


@project_bp.route("/projects/<int:project_id>/executions", methods=["GET"])
def listar_ejecuciones(project_id):
    """Lista ejecuciones de un proyecto."""
    executions = Execution.query.filter_by(project_id=project_id).order_by(Execution.created_at.desc()).limit(50).all()
    return jsonify([e.to_dict() for e in executions])


@project_bp.route("/projects/<int:project_id>/download", methods=["GET"])
def descargar_excel(project_id):
    """Descarga Excel de una ejecución."""
    execution_id = request.args.get("execution_id", type=int)

    if execution_id:
        execution = Execution.query.filter_by(id=execution_id, project_id=project_id).first()
    else:
        execution = Execution.query.filter(
            Execution.project_id == project_id,
            Execution.excel_path.isnot(None)
        ).order_by(Execution.created_at.desc()).first()

    if execution and execution.excel_path and os.path.exists(execution.excel_path):
        return send_file(execution.excel_path, as_attachment=True)

    return jsonify({"error": "No hay Excel disponible"}), 404


@project_bp.route("/projects/<int:project_id>/logs", methods=["GET"])
def obtener_logs(project_id):
    """Logs en tiempo real de la ejecución activa."""
    execution_id = request.args.get("execution_id", type=int)
    execution_service = current_app.config.get("EXECUTION_SERVICE")

    if not execution_service:
        return jsonify({"logs": ""})

    if execution_id:
        logs = execution_service.get_logs(execution_id)
    else:
        active = Execution.query.filter_by(project_id=project_id, status="ejecutando").first()
        if active:
            logs = execution_service.get_logs(active.id)
        else:
            last = Execution.query.filter_by(project_id=project_id).order_by(Execution.created_at.desc()).first()
            logs = (last.logs or "") if last else ""

    return jsonify({"logs": logs})


# ═══════════════ DASHBOARD ═══════════════

@project_bp.route("/dashboard", methods=["GET"])
def dashboard():
    """Estado global: todos los proyectos con ejecuciones activas."""
    activas = Execution.query.filter_by(status="ejecutando").all()

    proyectos_activos = []
    for exec in activas:
        project = db.session.get(Project, exec.project_id)
        if project:
            execution_service = current_app.config.get("EXECUTION_SERVICE")
            estado = exec.to_estado()
            if execution_service:
                estado["logs"] = execution_service.get_logs(exec.id)
            proyectos_activos.append({
                "project": project.to_dict_simple(),
                "execution": estado,
            })

    return jsonify({
        "activos": len(proyectos_activos),
        "proyectos": proyectos_activos,
    })
