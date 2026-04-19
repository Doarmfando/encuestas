"""
Generación de respuestas concretas a partir de configuración de perfil.
Solo responsabilidad: traducir config del perfil + estructura del formulario → valores.
Para agregar soporte a un nuevo tipo de pregunta: agregar un elif en _valor_para_tipo.
"""
import random
from app.services.analysis.survey_preparator import es_escala
from app.services.generation.text_inferrer import infer_text_value
from app.utils.text_normalizer import normalize_for_matching


_PATRONES_LIKERT = [
    {"nunca", "casi nunca", "a veces", "muchas veces", "siempre"},
    {"nunca", "raramente", "a veces", "frecuentemente", "siempre"},
    {"muy en desacuerdo", "en desacuerdo", "neutral", "de acuerdo", "muy de acuerdo"},
    {"totalmente en desacuerdo", "en desacuerdo", "ni de acuerdo ni en desacuerdo", "de acuerdo", "totalmente de acuerdo"},
    {"nada", "poco", "algo", "bastante", "mucho"},
    {"never", "rarely", "sometimes", "often", "always"},
]


def _es_likert(opciones: list) -> bool:
    if len(opciones) < 3:
        return False
    lower = {o.lower().strip() for o in opciones}
    return any(len(lower & patron) >= 3 for patron in _PATRONES_LIKERT)


class ResponseGenerator:
    """Genera respuestas concretas por pregunta.

    Para agregar un nuevo tipo de campo (ej. 'archivo'), agregar un caso en
    `_valor_para_tipo`. Para cambiar cómo se busca la config del perfil,
    editar `_buscar_config`. Solo este archivo cambia.
    """

    def generar(self, perfil: dict, estructura: dict, tendencia: dict) -> dict:
        """Genera el dict de respuesta completo para todas las páginas."""
        respuesta: dict = {"paginas": []}
        respuestas_perfil = perfil.get("respuestas", {})

        for pagina in estructura.get("paginas", []):
            respuestas_pagina = []
            for pregunta in pagina.get("preguntas", []):
                tipo = pregunta["tipo"]
                if tipo == "informativo":
                    continue
                texto = pregunta["texto"]
                opciones = pregunta.get("opciones", [])
                config = self._buscar_config(respuestas_perfil, texto)
                valor = self._valor_para_tipo(tipo, texto, opciones, config, tendencia, pregunta)
                if valor is not None:
                    respuestas_pagina.append({
                        "pregunta": texto,
                        "tipo": tipo,
                        "valor": valor,
                        "opciones_disponibles": opciones,
                    })

            respuesta["paginas"].append({
                "numero": pagina.get("numero", 0),
                "respuestas": respuestas_pagina,
                "botones": pagina.get("botones", []),
            })

        return respuesta

    def garantizar_obligatorias(self, respuesta: dict, estructura: dict) -> dict:
        """Rellena selecciones múltiples obligatorias que quedaron vacías."""
        preguntas_idx: dict = {}
        for pagina in estructura.get("paginas", []):
            for pregunta in pagina.get("preguntas", []):
                clave = normalize_for_matching(pregunta.get("texto", ""))
                if clave:
                    preguntas_idx[clave] = pregunta

        for pagina in respuesta.get("paginas", []):
            for r in pagina.get("respuestas", []):
                pregunta = preguntas_idx.get(normalize_for_matching(r.get("pregunta", "")), {})
                if pregunta.get("tipo") != "seleccion_multiple" or not pregunta.get("obligatoria"):
                    continue
                valor = r.get("valor")
                if isinstance(valor, list) and valor:
                    continue
                opciones = r.get("opciones_disponibles") or pregunta.get("opciones") or []
                if opciones:
                    r["valor"] = [random.choice(opciones)]

        return respuesta

    # ── privados ──────────────────────────────────────────────────────────────

    def _valor_para_tipo(
        self, tipo: str, texto: str, opciones: list, config: dict | None, tendencia: dict, pregunta: dict = None
    ):
        if config:
            return self._generar_segun_config(config, opciones, pregunta_tipo=tipo, pregunta=pregunta)

        if tipo in ("opcion_multiple", "seleccion_multiple") and opciones:
            if _es_likert(opciones) or es_escala(tipo, opciones):
                dist = self._distribucion(tendencia, len(opciones))
                return random.choices(opciones, weights=dist)[0]
            return random.choice(opciones)

        if tipo in ("escala_lineal", "escala", "likert", "rating", "matriz") and opciones:
            dist = self._distribucion(tendencia, len(opciones))
            filas = pregunta.get("filas", []) if pregunta else []
            if filas:
                return {fila: random.choices(opciones, weights=dist)[0] for fila in filas}
            return random.choices(opciones, weights=dist)[0]

        if tipo == "matriz_checkbox" and opciones:
            filas = pregunta.get("filas", []) if pregunta else []
            if filas:
                return {fila: [random.choice(opciones)] for fila in filas}
            return [random.choice(opciones)]

        if tipo == "numero":
            return str(random.randint(18, 60))

        if tipo in ("texto", "parrafo"):
            return infer_text_value(texto)

        if tipo == "desplegable" and opciones:
            return random.choice(opciones)

        if tipo == "fecha":
            return f"2026-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"

        if tipo == "hora":
            return f"{random.randint(6, 22):02d}:{random.choice(['00', '15', '30', '45'])}"

        return None

    def _generar_segun_config(self, config: dict, opciones_disponibles: list, pregunta_tipo: str | None = None, pregunta: dict = None):
        tipo = config.get("tipo", "aleatorio")

        valor_base = None
        if tipo == "fijo":
            valor_base = config.get("valor", "")
        elif tipo == "rango":
            valor_base = str(random.randint(config.get("min", 0), config.get("max", 100)))
        elif tipo == "aleatorio":
            opciones = config.get("opciones", {})
            if opciones:
                items, pesos = list(opciones.keys()), list(opciones.values())
                valor_base = random.choices(items, weights=pesos)[0]
            else:
                valor_base = random.choice(opciones_disponibles) if opciones_disponibles else ""
        elif tipo in ("multiple", "seleccion_multiple_condicionada"):
            valor_base = self._generar_multiple(config, opciones_disponibles)
        else:
            valor_base = [] if pregunta_tipo in ("seleccion_multiple", "matriz_checkbox") else ""

        if pregunta_tipo in ("matriz", "matriz_checkbox", "likert") and pregunta:
            filas = pregunta.get("filas", [])
            if filas:
                resultado = {}
                for fila in filas:
                    if tipo == "aleatorio":
                        opciones_cfg = config.get("opciones", {})
                        if opciones_cfg:
                            items, pesos = list(opciones_cfg.keys()), list(opciones_cfg.values())
                            val = random.choices(items, weights=pesos)[0]
                        else:
                            val = random.choice(opciones_disponibles) if opciones_disponibles else ""
                        resultado[fila] = [val] if pregunta_tipo == "matriz_checkbox" else val
                    else:
                        resultado[fila] = valor_base
                return resultado

        return valor_base

    def _generar_multiple(self, config: dict, opciones_disponibles: list) -> list:
        patrones = config.get("patrones", [])
        if isinstance(patrones, dict):
            claves = [k for k, v in patrones.items() if v and v > 0]
            pesos = [patrones[k] for k in claves]
            if claves:
                elegido = random.choices(claves, weights=pesos)[0]
                return self._resolver_patron(elegido, opciones_disponibles)
        elif isinstance(patrones, list) and patrones:
            validos = [p for p in patrones if p.get("peso", 0) > 0]
            if validos:
                elegido = random.choices(validos, weights=[p.get("peso", 1) for p in validos])[0]
                return self._resolver_patron(
                    elegido.get("valores", elegido.get("valor", [])), opciones_disponibles
                )
        return []

    def _resolver_patron(self, patron, opciones_disponibles: list) -> list:
        import re
        if patron is None:
            return []
        if isinstance(patron, list):
            return [str(v).strip() for v in patron if str(v).strip()]
        if isinstance(patron, dict):
            valores = patron.get("valores", patron.get("valor"))
            return self._resolver_patron(valores, opciones_disponibles)

        texto = str(patron).strip()
        if not texto:
            return []

        texto_norm = normalize_for_matching(texto)
        if texto_norm in {"sin_dias", "sin_dia", "ninguno", "ninguna", "vacio", "vacia", "none", "empty"}:
            return []

        if "|" in texto or "," in texto:
            return [p.strip() for p in re.split(r"[|,]", texto) if p.strip()]

        matched = re.match(r"^(\d+)(?:\s*[_-]?\s*dias?)?$", texto_norm)
        if matched and opciones_disponibles:
            cantidad = min(int(matched.group(1)), len(opciones_disponibles))
            return random.sample(list(opciones_disponibles), cantidad) if cantidad > 0 else []

        target = normalize_for_matching(texto)
        for opcion in opciones_disponibles:
            if normalize_for_matching(opcion) == target:
                return [opcion]
        return []

    def _distribucion(self, tendencia: dict, num_opciones: int) -> list:
        distribuciones = tendencia.get("distribuciones", {})
        clave = str(num_opciones)
        if clave in distribuciones:
            return distribuciones[clave]

        distribucion = tendencia.get("distribucion")
        if distribucion:
            return self._ajustar_distribucion(distribucion, num_opciones)

        return [1] * num_opciones

    def _ajustar_distribucion(self, distribucion: list, num_opciones: int) -> list:
        if len(distribucion) == num_opciones:
            return distribucion
        n_orig = len(distribucion)
        resultado = [0.0] * num_opciones
        for i in range(num_opciones):
            inicio = i * n_orig / num_opciones
            fin = (i + 1) * n_orig / num_opciones
            for j in range(n_orig):
                overlap = min(j + 1, fin) - max(j, inicio)
                if overlap > 0:
                    resultado[i] += distribucion[j] * overlap
        total_orig = sum(distribucion)
        total_nuevo = sum(resultado)
        if total_nuevo > 0:
            resultado = [r * total_orig / total_nuevo for r in resultado]
        return resultado

    def _buscar_config(self, respuestas_perfil: dict, texto: str) -> dict | None:
        """Busca la config de una pregunta con fallback a match normalizado."""
        if texto in respuestas_perfil:
            return respuestas_perfil[texto]

        texto_lower = texto.lower().strip()
        for key, config in respuestas_perfil.items():
            key_lower = key.lower().strip()
            if key_lower and (texto_lower.startswith(key_lower) or key_lower.startswith(texto_lower)):
                return config

        texto_norm = normalize_for_matching(texto)
        if texto_norm:
            for key, config in respuestas_perfil.items():
                key_norm = normalize_for_matching(key)
                if key_norm and (texto_norm == key_norm
                                 or texto_norm.startswith(key_norm)
                                 or key_norm.startswith(texto_norm)):
                    return config

        return None
