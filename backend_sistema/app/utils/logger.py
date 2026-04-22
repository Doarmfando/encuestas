"""
Factory centralizada de loggers.
Uso: logger = get_logger(__name__)
Produce logger con el nombre del módulo para filtrar en producción.
"""
import logging


def get_logger(name: str) -> logging.Logger:
    """Retorna un logger estándar para el módulo dado."""
    return logging.getLogger(name)
