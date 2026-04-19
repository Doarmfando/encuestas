"""
Corrección y generación de reglas de dependencia entre preguntas.
Solo responsabilidad: validar y corregir reglas. Para agregar un nuevo patrón de regla
automática (ej. detectar preguntas de embarazo): solo editar este archivo.
"""
import re
from app.utils.fuzzy_matcher import find_best_match


class RulesManager:
    """Gestiona las reglas de dependencia entre preguntas del formulario.

    Para agregar un nuevo patrón de regla automática, agregar un método
    _detectar_* y llamarlo desde generar_reglas_fallback. Nada más cambia.
    """

    def corregir_reglas(self, reglas: list, ref_map: dict) -> list:
        """Corrige nombres de preguntas en las reglas para que coincidan con el formulario."""
        ref_textos = list(ref_map.keys())
        corregidas = []

        for regla in reglas:
            si_preg = regla.get("si_pregunta", "")
            entonces_preg = regla.get("entonces_pregunta", "")

            regla["si_pregunta"] = find_best_match(si_preg, ref_textos, threshold=0.7) or si_preg
            regla["entonces_pregunta"] = find_best_match(entonces_preg, ref_textos, threshold=0.7) or entonces_preg
            regla.setdefault("operador", "igual")
            regla.setdefault("entonces_excluir", [])
            regla.setdefault("entonces_forzar", None)

            corregidas.append(regla)

        return corregidas

    def generar_reglas_fallback(self, preguntas: list) -> list:
        """Genera reglas de dependencia básicas detectando patrones comunes en el formulario."""
        reglas: list = []
        reglas.extend(self._detectar_hijos(preguntas))
        reglas.extend(self._detectar_empleo(preguntas))
        return reglas

    # ── detectores de patrones ────────────────────────────────────────────────

    def _detectar_hijos(self, preguntas: list) -> list:
        reglas = []
        for preg in preguntas:
            texto_lower = preg["texto"].lower()
            opciones = preg.get("opciones", [])
            opciones_lower = [o.lower() for o in opciones]

            if re.search(r'\bhijos?\b', texto_lower) and ("sí" in opciones_lower or "si" in opciones_lower or "no" in opciones_lower):
                for otra in preguntas:
                    otra_lower = otra["texto"].lower()
                    if otra["texto"] != preg["texto"] and re.search(r'\bhijos?\b', otra_lower) and otra.get("tipo") in ("numero", "texto"):
                        reglas.append({
                            "si_pregunta": preg["texto"],
                            "si_valor": next((o for o in opciones if o.lower() == "no"), "No"),
                            "operador": "igual",
                            "entonces_pregunta": otra["texto"],
                            "entonces_forzar": "0",
                            "entonces_excluir": [],
                        })
        return reglas

    def _detectar_empleo(self, preguntas: list) -> list:
        reglas = []
        for preg in preguntas:
            texto_lower = preg["texto"].lower()
            opciones = preg.get("opciones", [])

            if re.search(r'\btrabaja\b|\bempleo\b|\bsituaci[oó]n laboral\b', texto_lower):
                for otra in preguntas:
                    if otra["texto"] == preg["texto"]:
                        continue
                    otra_lower = otra["texto"].lower()
                    if re.search(r'\bocupaci[oó]n\b|\bcargo\b|\bempresa\b|\bdonde trabaja\b', otra_lower):
                        no_val = next((o for o in opciones if "no" in o.lower() and len(o) < 15), None)
                        if no_val:
                            reglas.append({
                                "si_pregunta": preg["texto"],
                                "si_valor": no_val,
                                "operador": "igual",
                                "entonces_pregunta": otra["texto"],
                                "entonces_forzar": "No aplica",
                                "entonces_excluir": [],
                            })
        return reglas
