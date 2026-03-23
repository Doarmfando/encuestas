"""
Rutas API para ejecución del bot.
"""
import os
import threading
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request, send_file, current_app
from app.database.connection import db
from app.database.models import Survey, AnalysisConfig, Execution

execution_bp = Blueprint("execution", __name__)


@execution_bp.route("/ejecutar", methods=["POST"])
def ejecutar():
    """Inicia la ejecución del bot."""
    # Verificar que no haya ejecución activa
    ejecutando = Execution.query.filter_by(status="ejecutando").first()
    if ejecutando:
        # Verificar si realmente hay un hilo corriendo
        execution_service = current_app.config.get("EXECUTION_SERVICE")
        if execution_service and not execution_service.is_running(ejecutando.id):
            # Ejecución huérfana: marcar como detenida
            ejecutando.status = "detenido"
            ejecutando.mensaje = "Detenido (sin hilo activo)"
            db.session.commit()
        else:
            return jsonify({"error": "Ya hay una ejecución en curso"}), 400

    data = request.json or {}
    survey_id = data.get("survey_id")
    cantidad = data.get("cantidad", 10)
    headless = data.get("headless", False)

    if cantidad < 1 or cantidad > 500:
        return jsonify({"error": "Cantidad debe ser entre 1 y 500"}), 400

    # Obtener survey
    if survey_id:
        survey = db.session.get(Survey, survey_id)
    else:
        survey = Survey.query.order_by(Survey.created_at.desc()).first()

    if not survey:
        return jsonify({"error": "Primero scrapea un formulario"}), 400

    # Obtener configuración activa
    config = AnalysisConfig.query.filter_by(survey_id=survey.id, is_active=True).first()
    if not config:
        return jsonify({"error": "Primero analiza el formulario"}), 400

    # Crear ejecución en BD
    execution = Execution(
        survey_id=survey.id,
        analysis_config_id=config.id,
        status="ejecutando",
        mensaje=f"Iniciando {cantidad} encuestas...",
        total=cantidad,
        headless=headless,
        started_at=datetime.now(timezone.utc),
    )
    db.session.add(execution)
    db.session.commit()

    # Lanzar hilo
    execution_service = current_app.config.get("EXECUTION_SERVICE")
    app = current_app._get_current_object()

    hilo = threading.Thread(
        target=execution_service.execute,
        args=(
            app,
            execution.id,
            survey.url,
            config.to_configuracion(),
            survey.to_estructura(),
            cantidad,
            headless,
        ),
    )
    hilo.daemon = True
    hilo.start()

    return jsonify({
        "mensaje": f"Bot iniciado: {cantidad} encuestas",
        "execution_id": execution.id,
    })


@execution_bp.route("/estado", methods=["GET"])
def obtener_estado():
    """Obtiene el estado de la ejecución más reciente o de una ejecución específica."""
    execution_id = request.args.get("execution_id", type=int)

    if execution_id:
        execution = db.session.get(Execution, execution_id)
    else:
        execution = Execution.query.order_by(Execution.created_at.desc()).first()

    if execution:
        estado = execution.to_estado()
        # Agregar logs en tiempo real si está ejecutando
        if execution.status == "ejecutando":
            execution_service = current_app.config.get("EXECUTION_SERVICE")
            if execution_service:
                estado["logs"] = execution_service.get_logs(execution.id)
        return jsonify(estado)

    # Retornar estado idle por defecto
    return jsonify({
        "fase": "idle",
        "mensaje": "Listo",
        "progreso": 0,
        "total": 0,
        "exitosas": 0,
        "fallidas": 0,
        "tiempo_transcurrido": "0s",
        "tiempo_por_encuesta": "0s",
        "excel": None,
    })


@execution_bp.route("/detener", methods=["POST"])
def detener():
    """Detiene la ejecución en curso."""
    data = request.json or {}
    execution_id = data.get("execution_id")

    if execution_id:
        execution = db.session.get(Execution, execution_id)
    else:
        execution = Execution.query.filter_by(status="ejecutando").first()

    if execution:
        execution_service = current_app.config.get("EXECUTION_SERVICE")
        execution_service.stop(execution.id)
        execution.status = "detenido"
        execution.mensaje = "Detenido"
        db.session.commit()

    return jsonify({"mensaje": "Detenido"})


@execution_bp.route("/descargar", methods=["GET"])
def descargar():
    """Descarga el Excel de la última ejecución o de una ejecución específica."""
    execution_id = request.args.get("execution_id", type=int)

    if execution_id:
        execution = db.session.get(Execution, execution_id)
    else:
        execution = Execution.query.filter(
            Execution.excel_path.isnot(None)
        ).order_by(Execution.created_at.desc()).first()

    if execution and execution.excel_path and os.path.exists(execution.excel_path):
        return send_file(execution.excel_path, as_attachment=True)

    return jsonify({"error": "No hay Excel"}), 404


@execution_bp.route("/executions", methods=["GET"])
def listar_executions():
    """Lista todas las ejecuciones."""
    survey_id = request.args.get("survey_id", type=int)
    query = Execution.query

    if survey_id:
        query = query.filter_by(survey_id=survey_id)

    executions = query.order_by(Execution.created_at.desc()).limit(50).all()
    return jsonify([e.to_dict() for e in executions])


@execution_bp.route("/logs", methods=["GET"])
def obtener_logs():
    """Obtiene los logs en tiempo real de una ejecución."""
    execution_id = request.args.get("execution_id", type=int)

    execution_service = current_app.config.get("EXECUTION_SERVICE")
    if not execution_service:
        return jsonify({"logs": ""})

    if execution_id:
        logs = execution_service.get_logs(execution_id)
    else:
        # Buscar ejecución activa
        active = Execution.query.filter_by(status="ejecutando").first()
        if active:
            logs = execution_service.get_logs(active.id)
        else:
            # Última ejecución completada
            last = Execution.query.order_by(Execution.created_at.desc()).first()
            logs = (last.logs or "") if last else ""

    return jsonify({"logs": logs})
