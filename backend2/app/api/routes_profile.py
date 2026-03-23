"""
Rutas API para análisis y gestión de perfiles/configuración.
"""
from flask import Blueprint, jsonify, request, current_app
from app.database.connection import db
from app.database.models import Survey, AnalysisConfig

profile_bp = Blueprint("profile", __name__)


@profile_bp.route("/analizar", methods=["POST"])
def analizar():
    """Analiza el formulario scrapeado con IA."""
    data = request.json or {}
    survey_id = data.get("survey_id")

    # Si no se pasa survey_id, usar la última encuesta
    if survey_id:
        survey = db.session.get(Survey, survey_id)
    else:
        survey = Survey.query.order_by(Survey.created_at.desc()).first()

    if not survey:
        return jsonify({"error": "Primero scrapea un formulario"}), 400

    try:
        ai_service = current_app.config.get("AI_SERVICE")
        if not ai_service:
            return jsonify({"error": "No hay servicio de IA configurado"}), 500

        from app.services.analyzer_service import AnalyzerService
        analyzer = AnalyzerService(ai_service)
        configuracion = analyzer.analyze(survey.to_estructura())

        # Desactivar configs anteriores
        AnalysisConfig.query.filter_by(survey_id=survey.id, is_active=True).update({"is_active": False})

        # Guardar nueva config
        analysis = AnalysisConfig(
            survey_id=survey.id,
            perfiles=configuracion.get("perfiles", []),
            reglas_dependencia=configuracion.get("reglas_dependencia", []),
            tendencias_escalas=configuracion.get("tendencias_escalas", []),
            ai_provider_used=ai_service.active_provider_name or "",
            is_active=True,
        )
        db.session.add(analysis)
        db.session.commit()

        result = configuracion.copy()
        result["id"] = analysis.id
        result["survey_id"] = survey.id
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@profile_bp.route("/configuracion", methods=["GET"])
def obtener_config():
    """Devuelve la configuración activa."""
    survey_id = request.args.get("survey_id", type=int)

    if survey_id:
        config = AnalysisConfig.query.filter_by(survey_id=survey_id, is_active=True).first()
    else:
        config = AnalysisConfig.query.filter_by(is_active=True).order_by(AnalysisConfig.created_at.desc()).first()

    if config:
        return jsonify(config.to_configuracion())
    return jsonify({"error": "No hay configuración"}), 404


@profile_bp.route("/configuracion", methods=["PUT"])
def actualizar_config():
    """Actualiza la configuración (perfiles, reglas, tendencias editadas por el usuario)."""
    nueva_config = request.json
    if not nueva_config:
        return jsonify({"error": "Configuración vacía"}), 400

    config_id = nueva_config.get("id")

    if config_id:
        config = db.session.get(AnalysisConfig, config_id)
    else:
        config = AnalysisConfig.query.filter_by(is_active=True).order_by(AnalysisConfig.created_at.desc()).first()

    if not config:
        return jsonify({"error": "No hay configuración para actualizar"}), 404

    if "perfiles" in nueva_config:
        config.perfiles = nueva_config["perfiles"]
    if "reglas_dependencia" in nueva_config:
        config.reglas_dependencia = nueva_config["reglas_dependencia"]
    if "tendencias_escalas" in nueva_config:
        config.tendencias_escalas = nueva_config["tendencias_escalas"]

    db.session.commit()
    return jsonify({"mensaje": "Configuración actualizada"})


@profile_bp.route("/surveys/<int:survey_id>/configs", methods=["GET"])
def listar_configs(survey_id):
    """Lista todas las configuraciones de una encuesta."""
    configs = AnalysisConfig.query.filter_by(survey_id=survey_id).order_by(AnalysisConfig.created_at.desc()).all()
    return jsonify([c.to_dict() for c in configs])


@profile_bp.route("/importar-config", methods=["POST"])
def importar_config():
    """Importa un JSON de configuración directamente (sin necesidad de IA).
    Crea un nuevo AnalysisConfig vinculado al survey actual."""
    data = request.json or {}
    survey_id = data.get("survey_id")

    if survey_id:
        survey = db.session.get(Survey, survey_id)
    else:
        survey = Survey.query.order_by(Survey.created_at.desc()).first()

    if not survey:
        return jsonify({"error": "Primero scrapea un formulario"}), 400

    perfiles = data.get("perfiles", [])
    reglas = data.get("reglas_dependencia", [])
    tendencias = data.get("tendencias_escalas", [])

    if not perfiles:
        return jsonify({"error": "El JSON debe tener al menos un perfil"}), 400

    # Desactivar configs anteriores
    AnalysisConfig.query.filter_by(survey_id=survey.id, is_active=True).update({"is_active": False})

    # Crear nueva config importada
    analysis = AnalysisConfig(
        survey_id=survey.id,
        nombre=data.get("nombre", "Importado"),
        perfiles=perfiles,
        reglas_dependencia=reglas,
        tendencias_escalas=tendencias,
        ai_provider_used="importado",
        is_active=True,
    )
    db.session.add(analysis)
    db.session.commit()

    result = analysis.to_configuracion()
    result["id"] = analysis.id
    result["survey_id"] = survey.id
    return jsonify(result)
