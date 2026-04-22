"""
Gestión del browser Playwright: configuración, contextos y selección de filler.
Para agregar soporte a una nueva plataforma: registrar su filler en _FILLER_REGISTRY.
"""
from app.automation.google_forms_filler import GoogleFormsFiller
from app.automation.microsoft_forms_filler import MicrosoftFormsFiller
from app.automation.navigation.selectors import validar_plataforma_soportada
from app.utils.browser_config import get_browser_context_options_from_flask

_FILLER_REGISTRY = {
    "google_forms": GoogleFormsFiller,
    "microsoft_forms": MicrosoftFormsFiller,
}


class BrowserManager:
    """Crea y gestiona contextos de browser Playwright."""

    def create_context(self, browser):
        opts = get_browser_context_options_from_flask()
        return browser.new_context(**opts)

    def get_filler(self, url: str):
        platform = validar_plataforma_soportada(url)
        name = platform.get("name")
        filler_cls = _FILLER_REGISTRY.get(name)
        if filler_cls:
            return filler_cls()
        raise ValueError("Solo se soportan formularios públicos de Google Forms y Microsoft Forms.")
