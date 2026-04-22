"""
Factory de la aplicación Flask.
"""
import logging
from flask import Flask
from flask_cors import CORS

from app.config import Config
from app.database.connection import db, init_db
from app.services.ai_service import AIService
from app.services.execution_service import ExecutionService
from app.services.generator_service import GeneratorService


def create_app(config_class=Config):
    """Crea y configura la aplicación Flask."""
    app = Flask(__name__)
    app.config.from_object(config_class)
    CORS(app)

    # Logging: INFO en producción, DEBUG si FLASK_DEBUG está activo
    log_level = logging.DEBUG if app.config.get("DEBUG") else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Handler que enruta logs al buffer del hilo de ejecución (frontend log stream)
    from app.services.execution.log_capture import ThreadLocalLogHandler
    thread_handler = ThreadLocalLogHandler()
    thread_handler.setLevel(logging.DEBUG)
    thread_handler.setFormatter(logging.Formatter("%(message)s"))
    logging.getLogger().addHandler(thread_handler)

    # Inicializar BD
    init_db(app)

    # Inicializar servicios
    ai_service = AIService()
    ai_service.init_app(app)

    generator = GeneratorService()
    execution_service = ExecutionService(ai_service=ai_service, generator=generator)

    # Guardar servicios en config para acceso desde rutas
    app.config["AI_SERVICE"] = ai_service
    app.config["EXECUTION_SERVICE"] = execution_service
    app.config["GENERATOR_SERVICE"] = generator

    # Manejadores globales de error
    from app.api.error_handlers import register_error_handlers
    register_error_handlers(app)

    # Registrar blueprints
    from app.api.routes_projects import project_bp
    from app.api.routes_scraping import scraping_bp
    from app.api.routes_analysis import analysis_bp
    from app.api.routes_configs import configs_bp
    from app.api.routes_execution import execution_bp
    from app.api.routes_config import config_bp
    from app.api.routes_docs import docs_bp

    app.register_blueprint(project_bp, url_prefix="/api")
    app.register_blueprint(scraping_bp, url_prefix="/api")
    app.register_blueprint(analysis_bp, url_prefix="/api")
    app.register_blueprint(configs_bp, url_prefix="/api")
    app.register_blueprint(execution_bp, url_prefix="/api")
    app.register_blueprint(config_bp, url_prefix="/api")
    app.register_blueprint(docs_bp)

    # Crear directorio de exports
    import os
    os.makedirs(app.config.get("EXPORT_DIR", "exports"), exist_ok=True)

    # Seed de prompts por defecto
    with app.app_context():
        from app.database.seed_prompts import seed_prompts
        seed_prompts(db)

    return app
