"""
Rutas de análisis IA: generar, previsualizar y aplicar configuraciones.
"""
from datetime import datetime
from flask import Blueprint, jsonify, request, current_app
from app.database.connection import db
from app.database.models import Project
from app.services.project_service import ProjectService, ProjectValidationError

analysis_bp = Blueprint("analysis", __name__)
_svc = ProjectService()


@analysis_bp.route("/projects/<int:project_id>/analyze", methods=["POST"])
def analizar_proyecto(project_id):
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Proyecto no encontrado"}), 404
    if not project.estructura:
        return jsonify({"error": "Primero scrapea el formulario"}), 400

    data = request.json or {}
    ai_service = current_app.config.get("AI_SERVICE")
    if not ai_service:
        return jsonify({"error": "No hay servicio de IA configurado"}), 500

    try:
        from app.services.analyzer_service import AnalyzerService
        analyzer = AnalyzerService(ai_service)
        configuracion = analyzer.analyze(project.to_estructura(), instrucciones_extra=data.get("instrucciones", ""))
        return jsonify({
            "preview": True,
            "project_id": project.id,
            "perfiles": configuracion.get("perfiles", []),
            "reglas_dependencia": configuracion.get("reglas_dependencia", []),
            "tendencias_escalas": configuracion.get("tendencias_escalas", []),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@analysis_bp.route("/projects/<int:project_id>/apply-config", methods=["POST"])
def aplicar_config_ia(project_id):
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Proyecto no encontrado"}), 404

    data = request.json or {}
    perfiles = data.get("perfiles", [])
    reglas = data.get("reglas_dependencia", [])
    tendencias = data.get("tendencias_escalas", [])

    try:
        _svc.validar_configuracion(perfiles, tendencias)
    except ProjectValidationError as e:
        return jsonify({"error": str(e)}), 400

    ai_service = current_app.config.get("AI_SERVICE")
    config, created = _svc.guardar_configuracion(
        project,
        nombre=data.get("nombre", "IA - " + datetime.now().strftime("%d/%m %H:%M")),
        perfiles=perfiles,
        reglas=reglas,
        tendencias=tendencias,
        ai_provider_used=ai_service.active_provider_name if ai_service else "",
    )
    return jsonify(config.to_dict()), 201 if created else 200


@analysis_bp.route("/projects/<int:project_id>/template-config", methods=["POST"])
def generar_template_config(project_id):
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Proyecto no encontrado"}), 404
    if not project.estructura:
        return jsonify({"error": "Primero scrapea el formulario"}), 400

    data = request.json or {}
    nombre = data.get("nombre", f"Plantilla - {datetime.now().strftime('%d/%m %H:%M')}")

    try:
        from app.services.analyzer_service import AnalyzerService
        analyzer = AnalyzerService(current_app.config.get("AI_SERVICE"))
        configuracion = analyzer._generar_fallback(project.to_estructura())
        config, created = _svc.guardar_configuracion(
            project,
            nombre=nombre,
            perfiles=configuracion.get("perfiles", []),
            reglas=configuracion.get("reglas_dependencia", []),
            tendencias=configuracion.get("tendencias_escalas", []),
            ai_provider_used="manual",
        )
        return jsonify(config.to_dict()), 201 if created else 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
