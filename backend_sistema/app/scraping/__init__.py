"""
Factory para obtener el scraper apropiado según la URL.
"""
from app.automation.navigation.selectors import (
    SUPPORTED_PLATFORM_NAMES,
    validar_plataforma_soportada,
)


def get_scraper(url: str, ai_service=None, force_platform: str | None = None):
    """Retorna el scraper apropiado para la URL dada.

    Si `force_platform` llega con un nombre soportado ("google_forms" o
    "microsoft_forms"), se ignora la detección automática por URL y se usa
    el scraper forzado. Útil cuando la URL viene de un shortener o formulario
    embebido que no matchea el patrón estándar.
    """
    if force_platform:
        if force_platform not in SUPPORTED_PLATFORM_NAMES:
            raise ValueError(
                f"force_platform inválido: '{force_platform}'. "
                f"Valores válidos: {sorted(SUPPORTED_PLATFORM_NAMES)}."
            )
        platform_name = force_platform
    else:
        platform_name = validar_plataforma_soportada(url)["name"]

    if platform_name == "google_forms":
        from app.scraping.google_forms import GoogleFormsScraper
        return GoogleFormsScraper()
    if platform_name == "microsoft_forms":
        from app.scraping.generic_scraper import GenericScraper
        return GenericScraper(ai_service)
    raise ValueError("Solo se soportan formularios públicos de Google Forms y Microsoft Forms.")
