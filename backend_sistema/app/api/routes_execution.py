"""
Rutas de ejecución: lanzar, monitorear, detener y descargar resultados.
"""
import os
import threading
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request, send_file, current_app
from app.automation.timing import DEFAULT_EXECUTION_PROFILE, resolve_execution_profile
from app.automation.navigation.selectors import validar_plataforma_soportada
from app.database.connection import db
from app.database.models import Project, Execution
from app.services.project_service import ProjectService

execution_bp = Blueprint("execution", __name__)
_svc = ProjectService()


@execution_bp.route("/projects/<int:project_id>/execute", methods=["POST"])
def ejecutar_proyecto(project_id):
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Proyecto no encontrado"}), 404
    if not project.estructura:
        return jsonify({"error": "Primero scrapea el formulario"}), 400

    config = project.get_active_config()
    if not config:
        return jsonify({"error": "No hay config activa"}), 400
    try:
        validar_plataforma_soportada(project.url)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

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

    if speed_profile in ("turbo", "turbo_plus") and not _svc.tiene_balanced_exitoso(project.id):
        return jsonify({
            "error": "Turbo/Turbo+ requiere una ejecucion balanced 100% exitosa previa",
        }), 400

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
        args=(app, execution.id, project.url, config.to_configuracion(),
              project.to_estructura(), cantidad, headless, speed_profile),
    )
    hilo.daemon = True
    hilo.start()

    return jsonify({
        "mensaje": f"Bot iniciado: {cantidad} encuestas ({speed_profile})",
        "execution_id": execution.id,
    })


@execution_bp.route("/projects/<int:project_id>/estado", methods=["GET"])
def estado_proyecto(project_id):
    execution_id = request.args.get("execution_id", type=int)
    if execution_id:
        execution = Execution.query.filter_by(id=execution_id, project_id=project_id).first()
    else:
        execution = Execution.query.filter_by(project_id=project_id).order_by(
            Execution.created_at.desc()
        ).first()

    if execution:
        estado = execution.to_estado()
        if execution.status == "ejecutando":
            execution_service = current_app.config.get("EXECUTION_SERVICE")
            if execution_service:
                estado["logs"] = execution_service.get_logs(execution.id)
        return jsonify(estado)

    return jsonify({
        "execution_id": None, "project_id": project_id,
        "fase": "idle", "mensaje": "Listo",
        "progreso": 0, "total": 0, "exitosas": 0, "fallidas": 0,
        "tiempo_transcurrido": "0s", "tiempo_por_encuesta": "0s",
        "excel": None, "logs": "",
    })


@execution_bp.route("/projects/<int:project_id>/stop", methods=["POST"])
def detener_proyecto(project_id):
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


@execution_bp.route("/projects/<int:project_id>/executions", methods=["GET"])
def listar_ejecuciones(project_id):
    executions = Execution.query.filter_by(project_id=project_id).order_by(
        Execution.created_at.desc()
    ).limit(50).all()
    return jsonify([e.to_dict() for e in executions])


@execution_bp.route("/projects/<int:project_id>/download", methods=["GET"])
def descargar_excel(project_id):
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


@execution_bp.route("/projects/<int:project_id>/logs", methods=["GET"])
def obtener_logs(project_id):
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
            last = Execution.query.filter_by(project_id=project_id).order_by(
                Execution.created_at.desc()
            ).first()
            logs = (last.logs or "") if last else ""

    return jsonify({"logs": logs})
