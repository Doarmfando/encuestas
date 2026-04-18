"""
Factory de la aplicación Flask.
"""
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

    # Registrar blueprints
    from app.api.routes_project import project_bp
    from app.api.routes_config import config_bp

    app.register_blueprint(project_bp, url_prefix="/api")
    app.register_blueprint(config_bp, url_prefix="/api")

    # Crear directorio de exports
    import os
    os.makedirs(app.config.get("EXPORT_DIR", "exports"), exist_ok=True)

    # Seed de prompts por defecto
    with app.app_context():
        from app.database.seed_prompts import seed_prompts
        seed_prompts(db)

    return app
