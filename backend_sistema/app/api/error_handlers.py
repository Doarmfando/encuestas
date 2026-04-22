"""
Manejadores globales de error para la aplicación Flask.
Garantiza que todos los errores retornen JSON y queden logueados.
Para agregar un error HTTP específico: añadir un @app.errorhandler(código) aquí.
"""
import logging
from werkzeug.exceptions import HTTPException
from flask import jsonify

logger = logging.getLogger(__name__)


def register_error_handlers(app) -> None:
    """Registra los manejadores de error en la app Flask."""

    @app.errorhandler(HTTPException)
    def http_error(e: HTTPException):
        """404, 405 y otros errores HTTP esperados → JSON limpio, sin log."""
        return jsonify({"error": e.description, "code": e.code}), e.code

    @app.errorhandler(Exception)
    def unhandled_error(e: Exception):
        """Cualquier excepción no capturada → JSON + log con stack trace completo."""
        logger.error("Error no manejado en la API: %s", e, exc_info=True)
        return jsonify({
            "error": "Error interno del servidor",
            "detail": str(e),
        }), 500
