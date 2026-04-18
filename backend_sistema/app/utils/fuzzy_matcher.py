"""
Matching fuzzy centralizado usando SequenceMatcher.
Consolida las 4 implementaciones dispersas en analyzer_service, generator_service
y ms_forms_filler que tenían thresholds y lógicas ligeramente distintas.
"""
from difflib import SequenceMatcher
from app.utils.text_normalizer import normalize_for_matching


def similarity(a: str, b: str) -> float:
    """Retorna ratio de similitud [0, 1] entre dos strings normalizados."""
    return SequenceMatcher(None, normalize_for_matching(a), normalize_for_matching(b)).ratio()


def find_best_match(texto: str, candidatos: list[str], threshold: float = 0.7) -> str | None:
    """Encuentra el candidato más similar a `texto`.

    Returns:
        El candidato con mayor ratio >= threshold, o None si ninguno califica.
    """
    if not texto or not candidatos:
        return None

    mejor: str | None = None
    mejor_ratio = 0.0
    texto_norm = normalize_for_matching(texto)

    for candidato in candidatos:
        ratio = SequenceMatcher(None, texto_norm, normalize_for_matching(candidato)).ratio()
        if ratio > mejor_ratio:
            mejor_ratio = ratio
            mejor = candidato

    return mejor if mejor_ratio >= threshold else None


def map_keys_fuzzy(
    source: dict,
    target_keys: list[str],
    threshold: float = 0.7,
) -> dict:
    """Re-mapea las claves de `source` a las más cercanas en `target_keys`.

    Útil para corregir nombres de preguntas/opciones que vienen de la IA con
    texto ligeramente distinto al formulario real.

    Args:
        source: dict con claves aproximadas.
        target_keys: claves de referencia correctas.
        threshold: mínimo ratio para aceptar el match.

    Returns:
        Nuevo dict con claves corregidas. Claves sin match mantienen su valor original.
    """
    resultado: dict = {}
    usadas: set[str] = set()
    target_lower = {normalize_for_matching(k): k for k in target_keys}

    for key, value in source.items():
        key_norm = normalize_for_matching(key)

        # Match exacto primero
        if key_norm in target_lower:
            real = target_lower[key_norm]
            resultado[real] = value
            usadas.add(real)
            continue

        # Fuzzy
        mejor: str | None = None
        mejor_ratio = 0.0
        for t_norm, t_real in target_lower.items():
            if t_real in usadas:
                continue
            ratio = SequenceMatcher(None, key_norm, t_norm).ratio()
            if ratio > mejor_ratio:
                mejor_ratio = ratio
                mejor = t_real

        if mejor and mejor_ratio >= threshold:
            resultado[mejor] = value
            usadas.add(mejor)
        else:
            resultado[key] = value  # mantener clave original si no hay match

    return resultado
