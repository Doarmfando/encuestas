"""
Normalización y corrección de respuestas que devuelve la IA.
Solo responsabilidad: convertir cualquier formato de respuesta IA al formato
interno correcto. Para agregar soporte a un nuevo tipo de respuesta: solo editar aquí.
"""
from app.utils.fuzzy_matcher import find_best_match, map_keys_fuzzy, similarity


_TIPO_ALIASES: dict[str, str] = {
    "opciones": "aleatorio",
    "multiple": "aleatorio",
    "seleccion": "aleatorio",
    "texto": "fijo",
    "escala": "aleatorio",
    "lista": "aleatorio",
    "select": "aleatorio",
    "choice": "aleatorio",
    "radio": "aleatorio",
    "checkbox": "aleatorio",
}


class ResponseNormalizer:
    """Corrige y normaliza respuestas de perfiles generadas por la IA.

    Para agregar un nuevo tipo de campo en el formulario (ej. 'fecha'), basta con:
    1. Agregar su alias en _TIPO_ALIASES si es necesario.
    2. Agregar un bloque elif en _normalizar_por_tipo_final.
    No hay que tocar el orquestador ni otros servicios.
    """

    def corregir_nombres_preguntas(self, respuestas: dict, ref_map: dict) -> dict:
        """Re-mapea claves de `respuestas` a los nombres reales del formulario."""
        ref_textos = list(ref_map.keys())
        corregidas: dict = {}

        for texto_ia, config in respuestas.items():
            if not texto_ia or not str(texto_ia).strip():
                continue
            if texto_ia in ref_map:
                corregidas[texto_ia] = config
                continue

            mejor_match = find_best_match(texto_ia, ref_textos, threshold=0.7)
            if mejor_match:
                ratio = similarity(texto_ia, mejor_match)
                if ratio < 1.0:
                    print(f"    [~] Corregido: '{texto_ia[:30]}' → '{mejor_match[:30]}' ({ratio:.0%})")
                corregidas[mejor_match] = config
            else:
                corregidas[texto_ia] = config

        return corregidas

    def corregir_respuesta(self, config: dict, ref: dict | None = None) -> dict:
        """Corrige una respuesta individual usando la referencia del formulario."""
        if not isinstance(config, dict):
            return {"tipo": "fijo", "valor": str(config)}

        tipo = _TIPO_ALIASES.get(config.get("tipo", ""), config.get("tipo", ""))
        config["tipo"] = tipo

        if ref:
            config, tipo = self._forzar_tipo_por_referencia(config, ref)

        return self._normalizar_por_tipo_final(config, tipo)

    def corregir_opciones(self, opciones_ia: dict, opciones_form: list) -> dict:
        """Mapea opciones IA a las opciones reales del formulario (fuzzy)."""
        if not isinstance(opciones_ia, dict):
            peso = round(100 / max(len(opciones_form), 1))
            return {op: peso for op in opciones_form}

        resultado = map_keys_fuzzy(opciones_ia, opciones_form, threshold=0.6)
        opciones_form_set = set(opciones_form)
        resultado = {k: v for k, v in resultado.items() if k in opciones_form_set}

        if not resultado:
            peso = round(100 / max(len(opciones_form), 1))
            return {op: peso for op in opciones_form}

        return resultado

    def generar_respuesta_default(self, ref_preg: dict) -> dict:
        """Genera respuesta por defecto cuando la IA no cubrió una pregunta."""
        tipo = ref_preg["tipo"]
        opciones = ref_preg.get("opciones", [])

        if tipo in ("opcion_multiple", "seleccion_multiple", "desplegable") and opciones:
            peso = round(100 / len(opciones))
            return {"tipo": "aleatorio", "opciones": {op: peso for op in opciones}}
        if tipo == "numero":
            return {"tipo": "rango", "min": 1, "max": 50}
        if tipo in ("texto", "parrafo"):
            return {
                "tipo": "aleatorio",
                "opciones": {
                    "Respuesta variante 1": 25,
                    "Respuesta variante 2": 25,
                    "Respuesta variante 3": 25,
                    "Respuesta variante 4": 25,
                },
            }
        return {"tipo": "fijo", "valor": ""}

    def normalizar_opciones(self, config: dict):
        """Normaliza probabilidades de opciones para que sumen exactamente 100."""
        opciones = config.get("opciones", {})
        if not isinstance(opciones, dict) or not opciones:
            return
        total = sum(opciones.values())
        if total > 0 and total != 100:
            keys = list(opciones.keys())
            values = [opciones[k] for k in keys]
            normalizados = ajustar_suma_exacta(values)
            config["opciones"] = dict(zip(keys, normalizados))

    def normalizar_frecuencias(self, items: list):
        """Normaliza el campo `frecuencia` de una lista de items para que sume 100."""
        total = sum(item.get("frecuencia", 0) for item in items)
        if total > 0 and total != 100:
            values = [item.get("frecuencia", 0) for item in items]
            normalizados = ajustar_suma_exacta(values)
            for item, value in zip(items, normalizados):
                item["frecuencia"] = value

    # ── privados ──────────────────────────────────────────────────────────────

    def _forzar_tipo_por_referencia(self, config: dict, ref: dict) -> tuple[dict, str]:
        tipo_ref = ref["tipo"]
        opciones_ref = ref.get("opciones", [])

        if tipo_ref in ("opcion_multiple", "seleccion_multiple", "desplegable"):
            config["tipo"] = "aleatorio"
            if opciones_ref:
                config["opciones"] = self.corregir_opciones(config.get("opciones", {}), opciones_ref)
        elif tipo_ref == "numero":
            config.update({"tipo": "rango", "min": config.get("min", 1), "max": config.get("max", 50)})
            config.pop("opciones", None)
            config.pop("valor", None)
        elif tipo_ref in ("texto", "parrafo"):
            if config.get("tipo") != "aleatorio" or not config.get("opciones"):
                valor = config.get("valor", "")
                config["tipo"] = "aleatorio"
                config["opciones"] = {valor: 100} if valor and isinstance(valor, str) else {"Respuesta ejemplo": 100}
                config.pop("valor", None)

        return config, config["tipo"]

    def _normalizar_por_tipo_final(self, config: dict, tipo: str) -> dict:
        if tipo == "aleatorio":
            return self._normalizar_aleatorio(config)
        if tipo == "fijo":
            config.setdefault("valor", "")
            config.pop("opciones", None)
            return config
        if tipo == "rango":
            config.setdefault("min", 0)
            config.setdefault("max", 100)
            config.pop("opciones", None)
            config.pop("valor", None)
            return config
        return self._inferir_tipo(config)

    def _normalizar_aleatorio(self, config: dict) -> dict:
        opciones = config.get("opciones", {})

        if isinstance(opciones, list):
            if opciones:
                peso = round(100 / len(opciones))
                config["opciones"] = {str(op): peso for op in opciones if op}
            else:
                valor = config.get("valor")
                if valor:
                    config["opciones"] = {str(valor): 100}
                else:
                    return {"tipo": "fijo", "valor": ""}

        if not isinstance(config.get("opciones"), dict) or not config["opciones"]:
            valor = config.get("valor")
            if valor and isinstance(valor, str):
                config["opciones"] = {valor: 100}
            else:
                return {"tipo": "fijo", "valor": ""}

        self.normalizar_opciones(config)
        config.pop("valor", None)
        return config

    def _inferir_tipo(self, config: dict) -> dict:
        if isinstance(config.get("opciones"), dict) and config["opciones"]:
            config["tipo"] = "aleatorio"
            self.normalizar_opciones(config)
        elif config.get("valor") is not None:
            config["tipo"] = "fijo"
        elif "min" in config and "max" in config:
            config["tipo"] = "rango"
        else:
            config.update({"tipo": "fijo", "valor": ""})
        return config


def ajustar_suma_exacta(values: list, target: int = 100, min_value: int = 1) -> list:
    """Ajusta una lista de enteros para que sumen exactamente `target`.

    Función pura exportada para reutilización en TendencyManager y otros.
    """
    if not values:
        return []
    total = sum(values)
    if total <= 0:
        values = [min_value] * len(values)
        total = sum(values)

    scaled = [max(min_value, round(v * target / total)) for v in values]
    diff = target - sum(scaled)

    while diff != 0:
        if diff > 0:
            idx = min(range(len(scaled)), key=lambda i: scaled[i])
            scaled[idx] += 1
            diff -= 1
        else:
            candidates = [i for i, v in enumerate(scaled) if v > min_value]
            if not candidates:
                break
            idx = max(candidates, key=lambda i: scaled[i])
            scaled[idx] -= 1
            diff += 1

    return scaled
