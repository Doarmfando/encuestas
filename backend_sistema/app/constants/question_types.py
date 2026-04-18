"""
Tipos de preguntas unificados para todo el sistema.
FUENTE ÚNICA DE VERDAD: cualquier módulo que necesite tipos importa desde aquí.
"""

# ============ TIPOS ESTÁNDAR DEL SISTEMA ============
# Todos los scrapers y fillers usan estos nombres internos.

TIPO_TEXTO = "texto"
TIPO_PARRAFO = "parrafo"
TIPO_NUMERO = "numero"
TIPO_OPCION_MULTIPLE = "opcion_multiple"
TIPO_SELECCION_MULTIPLE = "seleccion_multiple"
TIPO_ESCALA_LINEAL = "escala_lineal"
TIPO_DESPLEGABLE = "desplegable"
TIPO_FECHA = "fecha"
TIPO_HORA = "hora"
TIPO_MATRIZ = "matriz"
TIPO_MATRIZ_CHECKBOX = "matriz_checkbox"
TIPO_LIKERT = "likert"
TIPO_NPS = "nps"
TIPO_RANKING = "ranking"
TIPO_ARCHIVO = "archivo"
TIPO_IMAGEN = "imagen"
TIPO_INFORMATIVO = "informativo"
TIPO_SECCION = "seccion"
TIPO_DESCONOCIDO = "desconocido"

# Tipos que NO se llenan (se saltan en el filler)
TIPOS_NO_LLENABLES = frozenset({
    TIPO_ARCHIVO, TIPO_IMAGEN, TIPO_INFORMATIVO, TIPO_SECCION,
})

# Tipos que usan tendencias de escala (no van en perfiles de IA)
TIPOS_ESCALA = frozenset({
    TIPO_ESCALA_LINEAL, TIPO_NPS, TIPO_LIKERT, TIPO_MATRIZ,
})

# Tipos de texto libre
TIPOS_TEXTO = frozenset({
    TIPO_TEXTO, TIPO_PARRAFO, TIPO_NUMERO,
})

# Tipos con opciones clickeables
TIPOS_OPCIONES = frozenset({
    TIPO_OPCION_MULTIPLE, TIPO_SELECCION_MULTIPLE, TIPO_DESPLEGABLE,
    TIPO_ESCALA_LINEAL, TIPO_NPS, TIPO_RANKING,
})


# ============ MAPEO GOOGLE FORMS ============
# Google Forms usa un número entero (item[3]) para identificar el tipo.

GOOGLE_FORMS_TYPE_MAP = {
    0: TIPO_TEXTO,              # Short answer
    1: TIPO_PARRAFO,            # Paragraph
    2: TIPO_OPCION_MULTIPLE,    # Multiple choice (radio)
    3: TIPO_DESPLEGABLE,        # Dropdown
    4: TIPO_SELECCION_MULTIPLE, # Checkboxes
    5: TIPO_ESCALA_LINEAL,      # Linear scale
    6: TIPO_INFORMATIVO,        # "Titulo y descripcion" bloque decorativo (NO es file upload)
    7: TIPO_MATRIZ,             # Multiple choice grid (radio grid)
    8: TIPO_SECCION,            # Salto de pagina / page break
    9: TIPO_FECHA,              # Date
    10: TIPO_HORA,              # Time
    11: TIPO_MATRIZ_CHECKBOX,   # Checkbox grid
    12: TIPO_NUMERO,            # Number (newer Forms)
    13: TIPO_ARCHIVO,           # File upload (newer Forms)
}


# ============ MAPEO MICROSOFT FORMS ============
# MS Forms usa strings en su API (question.type). Los detalles finos (multi-select,
# número, multilinea, rating) viven en questionInfo (JSON string).

def _parse_ms_question_info(question: dict) -> dict:
    """Parsea questionInfo que puede venir como JSON string o dict."""
    import json
    qi = question.get("questionInfo")
    if not qi:
        return {}
    if isinstance(qi, dict):
        return qi
    if isinstance(qi, str):
        try:
            return json.loads(qi)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def map_ms_forms_type(question: dict) -> str:
    """Mapea el tipo de pregunta de MS Forms al formato estándar.

    Args:
        question: dict del JSON de la API de MS Forms. Lee tanto campos de alto
                  nivel (type, allowMultipleValues) como questionInfo anidado
                  (ChoiceType, IsNumber, Multiline, RatingShape, etc.).
    """
    q_type = (question.get("type", "") or "").lower()
    q_subtype = (question.get("questionFormat", "") or "").lower()
    qi = _parse_ms_question_info(question)

    if "choice" in q_type:
        # ChoiceType: 1 = radio (Single), 2 = checkbox (Multiple).
        # allowMultipleValues es el flag moderno; algunos forms también usan
        # allowMultipleSelections.
        choice_type = qi.get("ChoiceType")
        allow_multiple = (
            choice_type == 2
            or bool(question.get("allowMultipleValues"))
            or bool(question.get("allowMultipleSelections"))
            or bool(qi.get("MultipleSelection"))
        )
        return TIPO_SELECCION_MULTIPLE if allow_multiple else TIPO_OPCION_MULTIPLE

    if "textfield" in q_type or "text" in q_type:
        is_number = (
            bool(qi.get("IsNumber"))
            or q_subtype in ("number", "numeric")
            or bool(question.get("isNumeric"))
        )
        if is_number:
            return TIPO_NUMERO
        is_long = (
            bool(qi.get("Multiline"))
            or bool(question.get("isLongText"))
            or q_subtype == "longtext"
        )
        return TIPO_PARRAFO if is_long else TIPO_TEXTO

    if "rating" in q_type:
        return TIPO_ESCALA_LINEAL
    if "date" in q_type:
        return TIPO_FECHA
    if "time" in q_type:
        return TIPO_HORA
    if "ranking" in q_type:
        return TIPO_RANKING
    if "nps" in q_type:
        return TIPO_NPS
    if "likert" in q_type or "matrix" in q_type:
        return TIPO_LIKERT
    if "file" in q_type or "upload" in q_type:
        return TIPO_ARCHIVO
    if "number" in q_type or "numeric" in q_type:
        return TIPO_NUMERO

    # Si tiene choices (API expandida o questionInfo.Choices), es opción múltiple.
    if question.get("choices") or qi.get("Choices"):
        return TIPO_OPCION_MULTIPLE

    return TIPO_TEXTO
