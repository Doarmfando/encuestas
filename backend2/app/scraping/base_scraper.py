"""
Clase base abstracta para scrapers de encuestas.
"""
from abc import ABC, abstractmethod


class BaseScraper(ABC):
    """Interfaz base para todos los scrapers."""

    @abstractmethod
    def scrape(self, url: str, headless: bool = True) -> dict:
        """Scrapea una encuesta y retorna su estructura normalizada.

        Returns:
            dict con keys: url, titulo, descripcion, paginas, total_preguntas,
                          requiere_login, plataforma
        """
        ...

    @staticmethod
    def resultado_vacio(url: str = "", plataforma: str = "desconocido") -> dict:
        """Crea un resultado vacío."""
        return {
            "url": url,
            "titulo": "",
            "descripcion": "",
            "paginas": [],
            "total_preguntas": 0,
            "requiere_login": False,
            "plataforma": plataforma,
        }
