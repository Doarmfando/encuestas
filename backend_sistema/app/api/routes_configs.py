"""
CRUD de configuraciones de proyecto.
"""
from flask import Blueprint, jsonify, request
from app.constants.limits import MIN_PERFILES, MAX_PERFILES, MIN_TENDENCIAS, MAX_TENDENCIAS
from app.database.connection import db
from app.database.models import Project, ProjectConfig
from app.services.project_service import ProjectService, ProjectValidationError

configs_bp = Blueprint("configs", __name__)
_svc = ProjectService()


@configs_bp.route("/projects/<int:project_id>/configs", methods=["GET"])
def listar_configs(project_id):
    configs = ProjectConfig.query.filter_by(project_id=project_id).order_by(
        ProjectConfig.is_active.desc(),
        ProjectConfig.updated_at.desc(),
        ProjectConfig.created_at.desc(),
    ).all()
    return jsonify([c.to_dict() for c in configs])


@configs_bp.route("/projects/<int:project_id>/configs", methods=["POST"])
def crear_config(project_id):
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

    config, created = _svc.guardar_configuracion(
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


@configs_bp.route("/projects/<int:project_id>/configs/<int:config_id>", methods=["PUT"])
def actualizar_config(project_id, config_id):
    config = ProjectConfig.query.filter_by(id=config_id, project_id=project_id).first()
    if not config:
        return jsonify({"error": "Config no encontrada"}), 404

    data = request.json or {}
    if "perfiles" in data:
        if len(data["perfiles"]) < MIN_PERFILES or len(data["perfiles"]) > MAX_PERFILES:
            return jsonify({"error": f"Se requieren entre {MIN_PERFILES} y {MAX_PERFILES} perfiles"}), 400
        config.perfiles = data["perfiles"]
    if "reglas_dependencia" in data:
        config.reglas_dependencia = data["reglas_dependencia"] or []
    if "tendencias_escalas" in data:
        if len(data["tendencias_escalas"]) < MIN_TENDENCIAS or len(data["tendencias_escalas"]) > MAX_TENDENCIAS:
            return jsonify({"error": f"Se requieren entre {MIN_TENDENCIAS} y {MAX_TENDENCIAS} tendencias"}), 400
        config.tendencias_escalas = data["tendencias_escalas"]
    if "nombre" in data:
        config.nombre = data["nombre"]

    db.session.commit()
    return jsonify(config.to_dict())


@configs_bp.route("/projects/<int:project_id>/configs/<int:config_id>/activate", methods=["PUT"])
def activar_config(project_id, config_id):
    config = ProjectConfig.query.filter_by(id=config_id, project_id=project_id).first()
    if not config:
        return jsonify({"error": "Config no encontrada"}), 404

    ProjectConfig.query.filter_by(project_id=project_id, is_active=True).update({"is_active": False})
    config.is_active = True
    db.session.commit()
    return jsonify({"mensaje": f"Config '{config.nombre}' activada"})


@configs_bp.route("/projects/<int:project_id>/configs/<int:config_id>", methods=["DELETE"])
def eliminar_config(project_id, config_id):
    total = ProjectConfig.query.filter_by(project_id=project_id).count()
    if total <= 1:
        return jsonify({"error": "No se puede eliminar la última config"}), 400

    config = ProjectConfig.query.filter_by(id=config_id, project_id=project_id).first()
    if not config:
        return jsonify({"error": "Config no encontrada"}), 404

    was_active = config.is_active
    db.session.delete(config)
    db.session.commit()

    if was_active:
        latest = ProjectConfig.query.filter_by(project_id=project_id).order_by(
            ProjectConfig.created_at.desc()
        ).first()
        if latest:
            latest.is_active = True
            db.session.commit()

    return jsonify({"mensaje": "Config eliminada"})
