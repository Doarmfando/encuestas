"""
Selectores CSS y patrones de texto para diferentes plataformas de encuestas.
Centralizado para el soporte real del producto: Google Forms y Microsoft Forms.
"""

GOOGLE_FORMS = {
    "name": "google_forms",
    "url_patterns": ["docs.google.com/forms", "forms.gle"],
    "radio": '[role="radio"]',
    "checkbox": '[role="checkbox"]',
    "text_input": 'input[type="text"], input[type="number"]',
    "textarea": "textarea",
    "listbox": '[role="listbox"]',
    "listitem": '[role="listitem"]',
    "option": '[role="option"]',
    "heading": '[role="heading"]',
    "list": '[role="list"]',
    "data_value": '[data-value="{value}"]',
    "submit_texts": ["Enviar", "Submit", "Envoyer", "Senden"],
    "next_texts": ["Siguiente", "Next", "Suivant", "Weiter"],
    "back_texts": ["Atrás", "Back", "Précédent", "Zurück"],
    "success_url_patterns": ["formResponse", "closedform"],
    "success_texts": [
        "se registró tu respuesta",
        "tu respuesta se ha registrado",
        "respuesta registrada",
        "your response has been recorded",
        "enviar otra respuesta",
        "submit another response",
        "otra respuesta",
    ],
}

MICROSOFT_FORMS = {
    "name": "microsoft_forms",
    "url_patterns": ["forms.office.com", "forms.microsoft.com"],
    "radio": '[role="radio"], input[type="radio"]',
    "checkbox": '[role="checkbox"], input[type="checkbox"]',
    "text_input": 'input[type="text"], input[type="number"]',
    "textarea": "textarea",
    "listbox": '[role="listbox"], select',
    "listitem": ".question-container, .office-form-question",
    "option": "option, [role='option']",
    "heading": "h1, .form-title",
    "submit_texts": ["Submit", "Enviar"],
    "next_texts": ["Next", "Siguiente"],
    "back_texts": ["Back", "Previous", "Atrás"],
    "success_texts": [
        "your response was submitted",
        "your responses were submitted successfully",
        "thanks!",
        "thank you",
        "gracias",
        "las respuestas se han enviado correctamente",
        "la respuesta se ha enviado correctamente",
        "enviar otra respuesta",
        "submit another response",
        "guardar mi respuesta",
    ],
}

# Selectores genéricos internos para estados sin URL o lectura parcial del DOM.
GENERIC = {
    "name": "generic",
    "url_patterns": [],
    "radio": 'input[type="radio"], [role="radio"]',
    "checkbox": 'input[type="checkbox"], [role="checkbox"]',
    "text_input": 'input[type="text"], input[type="email"], input[type="number"], input[type="tel"]',
    "textarea": "textarea",
    "listbox": 'select, [role="listbox"]',
    "option": "option, [role='option']",
    "submit_texts": ["Submit", "Enviar", "Send", "Confirmar", "Finalizar", "Done"],
    "next_texts": ["Next", "Siguiente", "Continue", "Continuar", "Forward", "Avanzar"],
    "back_texts": ["Back", "Previous", "Atrás", "Anterior"],
    "success_texts": [
        "thank you", "gracias", "submitted", "enviado",
        "recorded", "registrado", "success", "completed",
    ],
}

UNSUPPORTED = {
    "name": "unsupported",
    "url_patterns": [],
    "radio": GENERIC["radio"],
    "checkbox": GENERIC["checkbox"],
    "text_input": GENERIC["text_input"],
    "textarea": GENERIC["textarea"],
    "listbox": GENERIC["listbox"],
    "option": GENERIC["option"],
    "submit_texts": GENERIC["submit_texts"],
    "next_texts": GENERIC["next_texts"],
    "back_texts": GENERIC["back_texts"],
    "success_texts": GENERIC["success_texts"],
}

SUPPORTED_PLATFORMS = [GOOGLE_FORMS, MICROSOFT_FORMS]
SUPPORTED_PLATFORM_NAMES = {platform["name"] for platform in SUPPORTED_PLATFORMS}


def detectar_plataforma(url: str) -> dict:
    """Detecta la plataforma soportada basándose en la URL."""
    if not url:
        return GENERIC

    url_lower = url.lower()
    for platform in SUPPORTED_PLATFORMS:
        for pattern in platform.get("url_patterns", []):
            if pattern in url_lower:
                return platform
    return UNSUPPORTED


def es_plataforma_soportada(url: str) -> bool:
    """Indica si la URL corresponde a una plataforma soportada."""
    return detectar_plataforma(url)["name"] in SUPPORTED_PLATFORM_NAMES


def validar_plataforma_soportada(url: str) -> dict:
    """Valida que la URL sea Google Forms o Microsoft Forms y retorna la plataforma."""
    platform = detectar_plataforma(url)
    if platform["name"] not in SUPPORTED_PLATFORM_NAMES:
        raise ValueError("Solo se soportan formularios públicos de Google Forms y Microsoft Forms.")
    return platform


def get_supported_platform_options() -> list[dict]:
    """Opciones amigables para exponer en settings/UI."""
    return [
        {"id": GOOGLE_FORMS["name"], "label": "Google Forms"},
        {"id": MICROSOFT_FORMS["name"], "label": "Microsoft Forms"},
    ]


def get_platform_selectors(platform_name: str) -> dict:
    """Obtiene selectores por nombre de plataforma."""
    for platform in SUPPORTED_PLATFORMS:
        if platform["name"] == platform_name:
            return platform
    if platform_name == GENERIC["name"]:
        return GENERIC
    return UNSUPPORTED
