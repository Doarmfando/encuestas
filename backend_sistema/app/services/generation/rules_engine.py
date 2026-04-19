"""
Motor de reglas de dependencia entre preguntas.
Solo responsabilidad: evaluar condiciones y aplicar cambios a respuestas generadas.
Para agregar un nuevo operador de condición (ej. 'entre'): solo agregar un caso
en `_evaluar_condicion`. No hay que tocar GeneratorService ni otros archivos.
"""
import random
import re
from app.utils.text_normalizer import normalize_for_matching


class RulesEngine:
    """Aplica reglas de dependencia sobre un dict de respuestas ya generadas.

    Para agregar un nuevo operador (ej. 'entre', 'es_nulo'), agregar un bloque
    `if operador == 'entre':` en _evaluar_condicion. Nada más cambia.
    """

    def aplicar(self, respuesta: dict, reglas: list) -> dict:
        if not reglas:
            return respuesta

        respuestas_planas, meta = self._indexar(respuesta)
        norm_map = self._normalizar_claves(respuestas_planas)
        cambios: dict = {}

        for regla in reglas:
            si_key = norm_map.get(normalize_for_matching(regla.get("si_pregunta", "")),
                                  regla.get("si_pregunta", ""))
            valor_actual = cambios.get(si_key, respuestas_planas.get(si_key, ""))

            if not self._evaluar_condicion(valor_actual, regla.get("operador", "igual"), regla.get("si_valor", "")):
                continue

            ent_key = norm_map.get(normalize_for_matching(regla.get("entonces_pregunta", "")),
                                   regla.get("entonces_pregunta", ""))
            valor_entonces = cambios.get(ent_key, respuestas_planas.get(ent_key, ""))
            opciones = meta.get(ent_key, {}).get("opciones_disponibles", [])

            forzar = regla.get("entonces_forzar")
            excluir = regla.get("entonces_excluir", [])
            permitir = regla.get("entonces_permitir", [])

            if forzar is not None:
                nuevo = self._resolver_forzar(forzar)
            elif excluir or permitir:
                nuevo = self._aplicar_restricciones(valor_entonces, opciones, excluir, permitir)
            else:
                continue

            cambios[ent_key] = nuevo
            respuestas_planas[ent_key] = nuevo

        cambios_norm = {normalize_for_matching(k): v for k, v in cambios.items()}
        for pagina in respuesta.get("paginas", []):
            for r in pagina.get("respuestas", []):
                pregunta = r["pregunta"]
                if pregunta in cambios:
                    r["valor"] = cambios[pregunta]
                else:
                    norm = normalize_for_matching(pregunta)
                    if norm in cambios_norm:
                        r["valor"] = cambios_norm[norm]

        return respuesta

    # ── evaluación de condiciones ──────────────────────────────────────────────

    def _evaluar_condicion(self, valor_actual, operador: str, si_valor) -> bool:
        operador = str(operador or "igual").strip().lower()

        if operador == "igual":
            return self._equivalentes(valor_actual, si_valor)
        if operador == "diferente":
            return not self._equivalentes(valor_actual, si_valor)
        if operador == "contiene":
            return self._contiene(valor_actual, si_valor)
        if operador == "no_contiene":
            return not self._contiene(valor_actual, si_valor)
        if operador == "cardinalidad_igual":
            try:
                return len(self._como_lista(valor_actual)) == int(si_valor)
            except (TypeError, ValueError):
                return False
        if operador == "cardinalidad_mayor":
            try:
                return len(self._como_lista(valor_actual)) > int(si_valor)
            except (TypeError, ValueError):
                return False
        if operador == "cardinalidad_menor":
            try:
                return len(self._como_lista(valor_actual)) < int(si_valor)
            except (TypeError, ValueError):
                return False
        if operador == "menor":
            try:
                return float(valor_actual) < float(si_valor)
            except (TypeError, ValueError):
                return False
        if operador == "mayor":
            try:
                return float(valor_actual) > float(si_valor)
            except (TypeError, ValueError):
                return False
        return False

    def _equivalentes(self, a, b) -> bool:
        if isinstance(a, list) or isinstance(b, list):
            return (sorted(normalize_for_matching(v) for v in self._como_lista(a))
                    == sorted(normalize_for_matching(v) for v in self._como_lista(b)))
        return normalize_for_matching(a) == normalize_for_matching(b)

    def _contiene(self, valor_actual, esperado) -> bool:
        esperado_norm = normalize_for_matching(esperado)
        if not esperado_norm:
            return False
        if isinstance(valor_actual, list):
            return esperado_norm in [normalize_for_matching(v) for v in self._como_lista(valor_actual)]
        return esperado_norm in normalize_for_matching(valor_actual)

    # ── aplicación de cambios ─────────────────────────────────────────────────

    def _resolver_forzar(self, forzar):
        if isinstance(forzar, list):
            return [str(v).strip() for v in forzar if str(v).strip()]
        if isinstance(forzar, (int, float)):
            return str(int(forzar)) if float(forzar).is_integer() else str(forzar)
        if isinstance(forzar, str):
            texto = forzar.strip()
            if not texto:
                return ""
            texto_norm = texto.replace("–", "-").replace("—", "-")
            m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", texto_norm)
            if m:
                a, b = int(m.group(1)), int(m.group(2))
                return str(random.randint(min(a, b), max(a, b)))
            if "|" in texto_norm or "," in texto_norm:
                partes = [p.strip() for p in re.split(r"[|,]", texto_norm) if p.strip()]
                return str(random.choice(partes)) if partes else texto
            return texto
        return str(forzar)

    def _aplicar_restricciones(self, valor_actual, opciones: list, excluir: list, permitir: list):
        excluir_norm = {normalize_for_matching(v) for v in excluir if str(v).strip()}
        permitir_norm = {normalize_for_matching(v) for v in permitir if str(v).strip()}

        opciones_validas = []
        vistos: set = set()
        for opcion in opciones:
            opcion_norm = normalize_for_matching(opcion)
            if not opcion_norm or opcion_norm in vistos:
                continue
            if excluir_norm and opcion_norm in excluir_norm:
                continue
            if permitir_norm and opcion_norm not in permitir_norm:
                continue
            opciones_validas.append(opcion)
            vistos.add(opcion_norm)

        if isinstance(valor_actual, list):
            return self._filtrar_lista(valor_actual, opciones_validas)

        actual_norm = normalize_for_matching(valor_actual)
        validas_norm = {normalize_for_matching(v) for v in opciones_validas}
        if actual_norm and actual_norm in validas_norm:
            return valor_actual
        return random.choice(opciones_validas) if opciones_validas else valor_actual

    def _filtrar_lista(self, valor_actual: list, opciones_validas: list) -> list:
        validas_norm = {normalize_for_matching(v) for v in opciones_validas}
        filtrados, usados = [], set()
        for item in self._como_lista(valor_actual):
            norm = normalize_for_matching(item)
            if norm in validas_norm and norm not in usados:
                filtrados.append(item)
                usados.add(norm)
        faltantes = max(0, len(self._como_lista(valor_actual)) - len(filtrados))
        candidatos = [v for v in opciones_validas if normalize_for_matching(v) not in usados]
        if faltantes and candidatos:
            random.shuffle(candidatos)
            filtrados.extend(candidatos[:faltantes])
        return filtrados

    # ── utilidades ────────────────────────────────────────────────────────────

    @staticmethod
    def _indexar(respuesta: dict) -> tuple[dict, dict]:
        planas, meta = {}, {}
        for pagina in respuesta.get("paginas", []):
            for r in pagina.get("respuestas", []):
                planas[r["pregunta"]] = r["valor"]
                meta[r["pregunta"]] = r
        return planas, meta

    @staticmethod
    def _normalizar_claves(respuestas_planas: dict) -> dict:
        norm_map = {}
        for pregunta in respuestas_planas:
            clave = normalize_for_matching(pregunta)
            if clave and clave not in norm_map:
                norm_map[clave] = pregunta
        return norm_map

    @staticmethod
    def _como_lista(valor) -> list[str]:
        if isinstance(valor, list):
            return [str(v).strip() for v in valor if str(v).strip()]
        if valor is None:
            return []
        texto = str(valor).strip()
        return [texto] if texto else []
