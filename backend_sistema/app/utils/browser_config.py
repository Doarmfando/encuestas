"""
Configuración centralizada de contexto Playwright.
Elimina la duplicación idéntica entre google_forms.py y generic_scraper.py.
"""
_DEFAULTS = {
    "locale": "es-PE",
    "timezone": "America/Lima",
    "viewport_width": 1280,
    "viewport_height": 720,
}


def get_browser_context_options(app_config: dict | None = None) -> dict:
    """Retorna kwargs para browser.new_context() con valores de config o defaults."""
    cfg = app_config or {}
    return {
        "locale": cfg.get("BROWSER_LOCALE", _DEFAULTS["locale"]),
        "timezone_id": cfg.get("BROWSER_TIMEZONE", _DEFAULTS["timezone"]),
        "viewport": {
            "width": cfg.get("BROWSER_VIEWPORT_WIDTH", _DEFAULTS["viewport_width"]),
            "height": cfg.get("BROWSER_VIEWPORT_HEIGHT", _DEFAULTS["viewport_height"]),
        },
    }


def get_browser_context_options_from_flask() -> dict:
    """Lee config de Flask (current_app) con fallback a defaults."""
    try:
        from flask import current_app
        return get_browser_context_options(current_app.config)
    except RuntimeError:
        return get_browser_context_options(None)
