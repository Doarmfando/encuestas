"""
Utilidades compartidas entre todos los handlers de Google Forms.
Para agregar un nuevo método de normalización o helper: solo editar aquí.
"""
import re
import time
import unicodedata
from difflib import SequenceMatcher

from app.automation.timing import pause_action


def normalize_match_text(value: str, strip_numbering: bool = False) -> str:
    """Normaliza texto para comparar opciones y preguntas sin acentos ni puntuación."""
    text = str(value or "").replace("\u00a0", " ")
    if strip_numbering:
        text = re.sub(r"^\s*\d+\s*[\.\)\-:]+\s*", "", text)
    text = text.replace("\u201c", '"').replace("\u201d", '"').replace("\u2019", "'")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[*]+", " ", text.lower())
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def prepare_scope(scope) -> None:
    """Hace visible el contenedor antes de interactuar con él."""
    try:
        scope.scroll_into_view_if_needed()
        time.sleep(0.15)
    except Exception:
        pass


def is_control_selected(control) -> bool:
    """Detecta si un radio/checkbox ya está marcado."""
    try:
        if (control.get_attribute("aria-checked") or "").lower() == "true":
            return True
        return bool(control.evaluate("el => Boolean(el.checked)"))
    except Exception:
        return False


def score_option_candidate(values: list[str], target: str) -> int:
    """Puntúa una opción candidata evitando matches ambiguos."""
    best = 0
    target_norm = normalize_match_text(target)
    for value in values:
        candidate = normalize_match_text(value)
        if not candidate:
            continue
        if candidate == target_norm:
            best = max(best, 1200)
            continue
        ratio = SequenceMatcher(None, target_norm, candidate).ratio()
        if ratio >= 0.97:
            best = max(best, int(ratio * 1000))
    return best


def click_control(control, runtime_config: dict | None = None) -> bool:
    """Intenta varias formas de click y verifica que el control quede activo."""
    if is_control_selected(control):
        return True

    for click_action in (
        lambda: control.click(),
        lambda: control.click(force=True),
        lambda: control.evaluate(
            """el => {
                el.scrollIntoView({block: "center", inline: "nearest"});
                el.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
                el.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
                el.click();
                el.dispatchEvent(new Event('input', {bubbles: true}));
                el.dispatchEvent(new Event('change', {bubbles: true}));
            }"""
        ),
    ):
        try:
            control.scroll_into_view_if_needed()
        except Exception:
            pass
        try:
            click_action()
            pause_action(runtime_config, multiplier=0.7)
            if is_control_selected(control):
                return True
        except Exception:
            continue
    return False
