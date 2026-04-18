"""
Normalización centralizada de texto para matching y comparación.
Consolida las 4 implementaciones duplicadas que había en filling_strategies,
ms_forms_filler, generator_service y analyzer_service.
"""
import re
import unicodedata


def normalize(texto: str, *, remove_accents: bool = True, lowercase: bool = True) -> str:
    """Normaliza texto: strip, unicode NFKD, sin tildes opcionales, lowercase opcional."""
    if not texto:
        return ""
    s = str(texto).strip()
    s = unicodedata.normalize("NFKD", s)
    if remove_accents:
        s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.lower() if lowercase else s


def normalize_for_matching(texto: str) -> str:
    """Normaliza para comparación: lowercase, sin tildes, sin puntuación extra, espacios simples."""
    s = normalize(texto)
    s = s.rstrip("*. :").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def normalize_for_key(texto: str) -> str:
    """Normaliza para usar como clave: sin puntuación, solo alfanumérico y espacios."""
    s = normalize(texto)
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()
