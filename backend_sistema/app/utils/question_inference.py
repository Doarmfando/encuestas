"""
Heuristicas compartidas para clasificar y llenar respuestas cortas.
"""
import re


SHORT_ANSWER_INPUT_SELECTORS = [
    'input[type="number"]',
    'input[inputmode="numeric"]',
    'input[inputmode="decimal"]',
    'input[role="spinbutton"]',
    'input[type="tel"]',
    'input[pattern*="0-9"]',
    'input[aria-label*="Tu respuesta" i]',
    'input[aria-label*="Your answer" i]',
    'input[type="text"]',
    'input:not([type])',
    'input:not([type="hidden"]):not([type="radio"]):not([type="checkbox"]):not([type="date"]):not([type="time"])',
]

NUMERIC_SHORT_ANSWER_INPUT_SELECTORS = [
    'input[type="number"]',
    'input[inputmode="numeric"]',
    'input[inputmode="decimal"]',
    'input[role="spinbutton"]',
    'input[type="tel"]',
    'input[pattern*="0-9"]',
    'input[type="text"]',
    'input:not([type])',
    'input:not([type="hidden"]):not([type="radio"]):not([type="checkbox"]):not([type="date"]):not([type="time"])',
]

TEXT_SHORT_ANSWER_INPUT_SELECTORS = [
    'input[aria-label*="Tu respuesta" i]',
    'input[aria-label*="Your answer" i]',
    'input[type="text"]',
    'input:not([type])',
    'input[type="number"]',
    'input[inputmode="numeric"]',
    'input[inputmode="decimal"]',
    'input[type="tel"]',
    'input:not([type="hidden"]):not([type="radio"]):not([type="checkbox"]):not([type="date"]):not([type="time"])',
]

_NUMERIC_QUESTION_RE = re.compile(
    r"\bedad\b|\bage\b|\ba[ñn]os?\b|\bdni\b|\bdocumento\b|\bc[eé]dula\b|\bcedula\b|"
    r"\btel[eé]fono\b|\bcelular\b|\bm[oó]vil\b|\bphone\b|\bc[oó]digo postal\b|\bzip\b|"
    r"\bn[uú]mero\b|\bnumero\b|\bcantidad\b|\bcu[aá]nt[oa]s?\b|\bcuantos?\b|"
    r"\bhow many\b|\bhow old\b|\bingresos?\b|\bsalario\b|\bsueldo\b|\bmonto\b|"
    r"\bprecio\b|\bpeso\b|\bestatura\b|\baltura\b|\btalla\b",
    re.IGNORECASE,
)

_NUMERIC_HINT_RE = re.compile(
    r"\b(number|numeric|decimal|digit|digits|entero|solo numeros|solo n[uú]meros|"
    r"spinbutton|age|edad|dni|telefono|tel[eé]fono|celular|zip|postal|cantidad|"
    r"cu[aá]nt[oa]s?|min|max|step)\b",
    re.IGNORECASE,
)


def normalize_text(value: str) -> str:
    """Normaliza whitespace y casing para comparar textos."""
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def looks_numeric_question(question_text: str = "", field_hints: str = "") -> bool:
    """Decide si una respuesta corta deberia tratarse como numerica."""
    question_norm = normalize_text(question_text)
    hints_norm = normalize_text(field_hints)
    combined = f"{question_norm} {hints_norm}".strip()

    if not combined:
        return False

    if any(token in hints_norm for token in (
        "type=number", "inputmode=numeric", "inputmode=decimal", "role=spinbutton"
    )):
        return True

    if "pattern=" in hints_norm and any(token in hints_norm for token in ("0-9", "digit", "\\d")):
        return True

    if any(token in hints_norm for token in ("min=", "max=", "step=")):
        return True

    return bool(_NUMERIC_QUESTION_RE.search(combined) or _NUMERIC_HINT_RE.search(hints_norm))


def infer_short_answer_type(question_text: str = "", field_hints: str = "") -> str:
    """Clasifica una respuesta corta como texto o numero."""
    return "numero" if looks_numeric_question(question_text, field_hints) else "texto"


def dummy_value_for_question(question_text: str = "", field_hints: str = "") -> str:
    """Devuelve un valor dummy coherente para destrabar preguntas obligatorias."""
    combined = normalize_text(f"{question_text} {field_hints}")
    if not looks_numeric_question(question_text, field_hints):
        return "respuesta"

    if re.search(r"\bedad\b|\bage\b|\ba[ñn]os?\b", combined):
        return "30"
    if re.search(r"\bdni\b|\bdocumento\b|\bc[eé]dula\b|\bcedula\b", combined):
        return "12345678"
    if re.search(r"\btel[eé]fono\b|\bcelular\b|\bm[oó]vil\b|\bphone\b", combined):
        return "987654321"
    if re.search(r"\bc[oó]digo postal\b|\bzip\b", combined):
        return "15001"
    if re.search(r"\ba[ñn]o\b|\byear\b", combined):
        return "2025"
    if re.search(r"\bpeso\b", combined):
        return "70"
    if re.search(r"\bestatura\b|\baltura\b", combined):
        return "170"
    if re.search(r"\bcantidad\b|\bcu[aá]nt[oa]s?\b|\bcuantos?\b", combined):
        return "2"
    return "30"
