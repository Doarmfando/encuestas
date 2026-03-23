"""
Rutas API para gestión de encuestas (scraping + estructura).
"""
from flask import Blueprint, jsonify, request, current_app
from app.database.connection import db
from app.database.models import Survey
from app.scraping import get_scraper

survey_bp = Blueprint("survey", __name__)


@survey_bp.route("/scrape", methods=["POST"])
def scrape():
    """Scrapea un formulario desde una URL."""
    data = request.json or {}
    url = data.get("url", "")

    if not url:
        return jsonify({"error": "URL requerida"}), 400

    try:
        ai_service = current_app.config.get("AI_SERVICE")
        scraper = get_scraper(url, ai_service)
        headless = data.get("headless", True)
        estructura = scraper.scrape(url, headless=headless)

        if estructura.get("requiere_login"):
            return jsonify({
                "error": "Este formulario requiere login. Solo se soportan formularios públicos."
            }), 400

        # Guardar en BD
        survey = Survey(
            url=estructura.get("url", url),
            titulo=estructura.get("titulo", ""),
            descripcion=estructura.get("descripcion", ""),
            plataforma=estructura.get("plataforma", "google_forms"),
            estructura={"paginas": estructura.get("paginas", [])},
            total_preguntas=estructura.get("total_preguntas", 0),
            requiere_login=False,
        )
        db.session.add(survey)
        db.session.commit()

        # Retornar formato compatible con frontend
        result = estructura.copy()
        result["id"] = survey.id
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@survey_bp.route("/estructura", methods=["GET"])
def obtener_estructura():
    """Devuelve la estructura de la última encuesta scrapeada."""
    survey = Survey.query.order_by(Survey.created_at.desc()).first()
    if survey:
        return jsonify(survey.to_estructura())
    return jsonify({"error": "No hay estructura"}), 404


@survey_bp.route("/surveys", methods=["GET"])
def listar_surveys():
    """Lista todas las encuestas scrapeadas."""
    surveys = Survey.query.order_by(Survey.created_at.desc()).all()
    return jsonify([s.to_dict() for s in surveys])


@survey_bp.route("/surveys/<int:survey_id>", methods=["GET"])
def obtener_survey(survey_id):
    """Obtiene una encuesta por ID."""
    survey = db.session.get(Survey, survey_id)
    if not survey:
        return jsonify({"error": "Encuesta no encontrada"}), 404
    return jsonify(survey.to_estructura())


@survey_bp.route("/surveys/<int:survey_id>", methods=["DELETE"])
def eliminar_survey(survey_id):
    """Elimina una encuesta y sus datos asociados."""
    survey = db.session.get(Survey, survey_id)
    if not survey:
        return jsonify({"error": "Encuesta no encontrada"}), 404
    db.session.delete(survey)
    db.session.commit()
    return jsonify({"mensaje": "Encuesta eliminada"})
