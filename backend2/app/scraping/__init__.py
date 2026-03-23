"""
Factory para obtener el scraper apropiado según la URL.
"""
from app.automation.navigation.selectors import detectar_plataforma


def get_scraper(url: str, ai_service=None):
    """Retorna el scraper apropiado para la URL dada."""
    platform = detectar_plataforma(url)

    if platform["name"] == "google_forms":
        from app.scraping.google_forms import GoogleFormsScraper
        return GoogleFormsScraper()
    else:
        from app.scraping.generic_scraper import GenericScraper
        return GenericScraper(ai_service)
