"""
Clase base abstracta para llenadores de formularios.
"""
from abc import ABC, abstractmethod


class BaseFiller(ABC):
    """Interfaz base para llenar formularios."""

    @abstractmethod
    def fill_form(self, page, respuesta_generada: dict, url: str, numero: int) -> tuple[bool, float]:
        """Llena un formulario completo y retorna (exito, tiempo_segundos)."""
        ...
