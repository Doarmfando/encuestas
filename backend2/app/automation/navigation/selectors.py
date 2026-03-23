"""
Selectores CSS y patrones de texto para diferentes plataformas de encuestas.
Centralizado para fácil extensión.
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
        "thanks!",
        "thank you",
        "gracias",
    ],
}

TYPEFORM = {
    "name": "typeform",
    "url_patterns": ["typeform.com"],
    "radio": '[role="radio"], button[role="option"]',
    "checkbox": '[role="checkbox"]',
    "text_input": 'input[type="text"], input[type="email"], input[type="number"]',
    "textarea": "textarea",
    "submit_texts": ["Submit", "Enviar"],
    "next_texts": ["OK", "Continue", "Next"],
    "back_texts": ["Back"],
    "success_texts": ["thank you", "gracias"],
}

# Selectores genéricos como fallback
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

ALL_PLATFORMS = [GOOGLE_FORMS, MICROSOFT_FORMS, TYPEFORM, GENERIC]


def detectar_plataforma(url: str) -> dict:
    """Detecta la plataforma de encuesta basándose en la URL."""
    url_lower = url.lower()
    for platform in ALL_PLATFORMS[:-1]:  # Excluir GENERIC
        for pattern in platform.get("url_patterns", []):
            if pattern in url_lower:
                return platform
    return GENERIC


def get_platform_selectors(platform_name: str) -> dict:
    """Obtiene selectores por nombre de plataforma."""
    for platform in ALL_PLATFORMS:
        if platform["name"] == platform_name:
            return platform
    return GENERIC
