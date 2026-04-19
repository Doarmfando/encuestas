"""
Gestión del browser Playwright: configuración, contextos y selección de filler.
Para agregar soporte a una nueva plataforma: registrar su filler en _FILLER_REGISTRY.
"""
from flask import current_app

from app.automation.google_forms_filler import GoogleFormsFiller
from app.automation.generic_filler import GenericFiller
from app.automation.navigation.selectors import validar_plataforma_soportada

_FILLER_REGISTRY = {
    "google_forms": GoogleFormsFiller,
    "microsoft_forms": GenericFiller,
}


class BrowserManager:
    """Crea y gestiona contextos de browser Playwright."""

    def get_config(self) -> dict:
        try:
            return {
                "locale": current_app.config.get("BROWSER_LOCALE", "es-PE"),
                "timezone": current_app.config.get("BROWSER_TIMEZONE", "America/Lima"),
                "vp_w": current_app.config.get("BROWSER_VIEWPORT_WIDTH", 1280),
                "vp_h": current_app.config.get("BROWSER_VIEWPORT_HEIGHT", 720),
                "pausa_min": current_app.config.get("PAUSA_MIN", 3.0),
                "pausa_max": current_app.config.get("PAUSA_MAX", 8.0),
            }
        except RuntimeError:
            return {
                "locale": "es-PE",
                "timezone": "America/Lima",
                "vp_w": 1280,
                "vp_h": 720,
                "pausa_min": 3.0,
                "pausa_max": 8.0,
            }

    def create_context(self, browser, config: dict):
        return browser.new_context(
            locale=config["locale"],
            timezone_id=config["timezone"],
            viewport={"width": config["vp_w"], "height": config["vp_h"]},
        )

    def get_filler(self, url: str):
        platform = validar_plataforma_soportada(url)
        name = platform.get("name")
        filler_cls = _FILLER_REGISTRY.get(name)
        if filler_cls:
            return filler_cls()
        raise ValueError("Solo se soportan formularios públicos de Google Forms y Microsoft Forms.")
