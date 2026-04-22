"""
Rutas de scraping y carga manual de estructura.
"""
from flask import Blueprint, jsonify, request, current_app
from app.automation.navigation.selectors import SUPPORTED_PLATFORM_NAMES, validar_plataforma_soportada
from app.database.connection import db
from app.database.models import Project
from app.services.project_service import ProjectService, ProjectValidationError

scraping_bp = Blueprint("scraping", __name__)
_svc = ProjectService()


@scraping_bp.route("/projects/<int:project_id>/scrape", methods=["POST"])
def scrape_proyecto(project_id):
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Proyecto no encontrado"}), 404

    data = request.json or {}
    force_platform = (data.get("force_platform") or "").strip().lower() or None

    if force_platform:
        if force_platform not in SUPPORTED_PLATFORM_NAMES:
            return jsonify({
                "error": f"force_platform inválido. Usa uno de: {sorted(SUPPORTED_PLATFORM_NAMES)}."
            }), 400
    else:
        try:
            validar_plataforma_soportada(project.url)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    try:
        ai_service = current_app.config.get("AI_SERVICE")
        from app.scraping import get_scraper
        scraper = get_scraper(project.url, ai_service, force_platform=force_platform)
        estructura = scraper.scrape(project.url, headless=data.get("headless", True))

        if estructura.get("requiere_login"):
            return jsonify({"error": "Formulario requiere login. Solo se soportan formularios públicos."}), 400

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


@scraping_bp.route("/projects/<int:project_id>/manual-structure", methods=["POST"])
def guardar_estructura_manual(project_id):
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Proyecto no encontrado"}), 404

    data = request.json or {}
    try:
        paginas_norm = _svc.normalizar_paginas_manual(data.get("paginas"))
    except ProjectValidationError as e:
        return jsonify({"error": str(e)}), 400

    try:
        platform = validar_plataforma_soportada(project.url)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    project.estructura = {"paginas": paginas_norm}
    project.plataforma = platform.get("name", "google_forms")
    project.total_preguntas = sum(len(p.get("preguntas", [])) for p in paginas_norm)
    project.requiere_login = False
    project.status = "scrapeado"
    db.session.commit()

    return jsonify({
        "project_id": project.id,
        "plataforma": project.plataforma,
        "titulo": project.nombre,
        "descripcion": project.descripcion,
        "paginas": paginas_norm,
        "total_preguntas": project.total_preguntas,
    })
