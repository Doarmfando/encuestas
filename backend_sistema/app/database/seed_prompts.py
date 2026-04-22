"""
Seed de prompts por defecto. Se insertan en la BD al iniciar si no existen.
"""
import logging

from app.ai.prompts import (
    PROMPT_SISTEMA_ANALISIS,
    PROMPT_ANALISIS_ENCUESTA,
    PROMPT_SISTEMA_SCRAPING,
    PROMPT_ANALIZAR_HTML,
    PROMPT_GENERAR_PERFIL,
)

logger = logging.getLogger(__name__)


DEFAULT_PROMPTS = {
    "system_analysis": {
        "nombre": "Sistema - Análisis de encuestas",
        "descripcion": "Prompt de sistema que define el rol del asistente al analizar encuestas. Define los tipos de respuesta y reglas.",
        "contenido": PROMPT_SISTEMA_ANALISIS,
    },
    "user_analysis": {
        "nombre": "Usuario - Análisis de encuestas",
        "descripcion": "Prompt que envía la estructura de la encuesta y pide generar perfiles, reglas y tendencias.",
        "contenido": PROMPT_ANALISIS_ENCUESTA,
    },
    "system_scraping": {
        "nombre": "Sistema - Scraping con IA",
        "descripcion": "Prompt de sistema para cuando la IA analiza HTML de formularios desconocidos.",
        "contenido": PROMPT_SISTEMA_SCRAPING,
    },
    "user_scraping": {
        "nombre": "Usuario - Scraping HTML",
        "descripcion": "Prompt que envía el HTML de una página para que la IA extraiga la estructura del formulario.",
        "contenido": PROMPT_ANALIZAR_HTML,
    },
    "generate_profile": {
        "nombre": "Generar perfil personalizado",
        "descripcion": "Prompt para generar un perfil individual basado en parámetros del usuario.",
        "contenido": PROMPT_GENERAR_PERFIL,
    },
}


def seed_prompts(db):
    """Inserta los prompts por defecto si no existen en la BD."""
    from app.database.models import PromptTemplate

    for slug, data in DEFAULT_PROMPTS.items():
        existing = PromptTemplate.query.filter_by(slug=slug).first()
        if not existing:
            prompt = PromptTemplate(
                slug=slug,
                nombre=data["nombre"],
                descripcion=data["descripcion"],
                contenido=data["contenido"],
                is_default=True,
            )
            db.session.add(prompt)
            logger.info("[seed] Prompt '%s' creado", slug)
        elif existing.is_default:
            existing.nombre = data["nombre"]
            existing.descripcion = data["descripcion"]
            existing.contenido = data["contenido"]

    db.session.commit()
