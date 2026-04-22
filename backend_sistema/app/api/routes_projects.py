"""
CRUD de proyectos y dashboard global.
"""
from flask import Blueprint, jsonify, request, current_app
from app.automation.navigation.selectors import validar_plataforma_soportada
from app.database.connection import db
from app.database.models import Project, Execution

project_bp = Blueprint("project", __name__)


@project_bp.route("/projects", methods=["POST"])
def crear_proyecto():
    data = request.json or {}
    nombre = data.get("nombre", "").strip()
    url = data.get("url", "").strip()

    if not nombre:
        return jsonify({"error": "Nombre requerido"}), 400
    if not url:
        return jsonify({"error": "URL requerida"}), 400
    try:
        validar_plataforma_soportada(url)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    project = Project(nombre=nombre, descripcion=data.get("descripcion", ""), url=url)
    db.session.add(project)
    db.session.commit()
    return jsonify(project.to_dict()), 201


@project_bp.route("/projects", methods=["GET"])
def listar_proyectos():
    projects = Project.query.order_by(Project.created_at.desc()).all()
    return jsonify([p.to_dict_simple() for p in projects])


@project_bp.route("/projects/<int:project_id>", methods=["GET"])
def obtener_proyecto(project_id):
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Proyecto no encontrado"}), 404
    result = project.to_dict()
    result["estructura"] = project.estructura
    return jsonify(result)


@project_bp.route("/projects/<int:project_id>", methods=["PUT"])
def actualizar_proyecto(project_id):
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Proyecto no encontrado"}), 404

    data = request.json or {}
    if "nombre" in data:
        project.nombre = data["nombre"]
    if "descripcion" in data:
        project.descripcion = data["descripcion"]
    if "url" in data:
        nueva_url = str(data["url"]).strip()
        try:
            validar_plataforma_soportada(nueva_url)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        project.url = nueva_url
        project.estructura = None
        project.status = "nuevo"

    db.session.commit()
    return jsonify(project.to_dict())


@project_bp.route("/projects/<int:project_id>", methods=["DELETE"])
def eliminar_proyecto(project_id):
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Proyecto no encontrado"}), 404

    ejecutando = Execution.query.filter_by(project_id=project_id, status="ejecutando").first()
    if ejecutando:
        return jsonify({"error": "No se puede eliminar, hay una ejecucion activa"}), 400

    db.session.delete(project)
    db.session.commit()
    return jsonify({"mensaje": "Proyecto eliminado"})


@project_bp.route("/dashboard", methods=["GET"])
def dashboard():
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
    return jsonify({"activos": len(proyectos_activos), "proyectos": proyectos_activos})
