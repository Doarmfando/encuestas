"""
Servicio de generación de respuestas basado en perfiles + reglas + tendencias.
"""
import random
import re

from app.utils.text_normalizer import normalize_for_matching as _norm_text


class GeneratorService:
    """Genera respuestas coherentes basadas en configuración de perfiles."""

    def generate(self, configuracion: dict, estructura_encuesta: dict) -> dict:
        """Genera una respuesta completa para el formulario."""
        perfiles = configuracion.get("perfiles", [])
        reglas = configuracion.get("reglas_dependencia", [])
        tendencias = configuracion.get("tendencias_escalas", [])

        perfil = self._elegir_perfil(perfiles)
        tendencia = self._elegir_tendencia(tendencias, perfil)
        respuesta = self._generar_desde_perfil(perfil, estructura_encuesta, tendencia)
        respuesta = self._aplicar_reglas(respuesta, reglas)
        respuesta = self._garantizar_respuestas_obligatorias(respuesta, estructura_encuesta)
        respuesta["_perfil"] = perfil.get("nombre", "desconocido")
        respuesta["_tendencia"] = tendencia.get("nombre", "desconocido")

        return respuesta

    def _elegir_perfil(self, perfiles: list) -> dict:
        if not perfiles:
            return {"nombre": "default", "respuestas": {}, "frecuencia": 100}
        pesos = [p.get("frecuencia", 10) for p in perfiles]
        return random.choices(perfiles, weights=pesos)[0]

    def _elegir_tendencia(self, tendencias: list, perfil: dict | None = None) -> dict:
        if not tendencias:
            return {"nombre": "neutro", "distribucion": [20, 20, 20, 20, 20], "frecuencia": 100}
        pesos = [t.get("frecuencia", 10) for t in tendencias]
        if perfil:
            preferencias = self._extraer_preferencias_tendencia(perfil, tendencias)
            if preferencias:
                pesos = [peso * preferencias.get(t.get("nombre", ""), 1) for peso, t in zip(pesos, tendencias)]
        return random.choices(tendencias, weights=pesos)[0]

    def _extraer_preferencias_tendencia(self, perfil: dict, tendencias: list) -> dict:
        """Sesga la eleccion de tendencias segun las sugerencias del perfil."""
        if not perfil or not tendencias:
            return {}

        nombres = [t.get("nombre", "") for t in tendencias if t.get("nombre")]
        preferencias = {nombre: 1 for nombre in nombres}

        sugerida = self._match_nombre(perfil.get("tendencia_sugerida"), nombres)
        if sugerida:
            preferencias[sugerida] = max(preferencias[sugerida], 4)

        preferidas = perfil.get("tendencias_preferidas", {})
        if isinstance(preferidas, dict):
            for nombre, peso in preferidas.items():
                match = self._match_nombre(nombre, nombres)
                if not match:
                    continue
                try:
                    preferencias[match] = max(preferencias[match], max(1, float(peso) / 25))
                except Exception:
                    preferencias[match] = max(preferencias[match], 2)

        return preferencias

    @staticmethod
    def _match_nombre(valor: str | None, candidatos: list[str]) -> str | None:
        """Empata nombres de tendencia por igualdad o similitud simple."""
        if not valor:
            return None
        if valor in candidatos:
            return valor

        valor_lower = str(valor).lower().strip()
        mejor = None
        mejor_ratio = 0
        for candidato in candidatos:
            candidato_lower = candidato.lower().strip()
            ratio = GeneratorService._similaridad_simple(valor_lower, candidato_lower)
            if ratio > mejor_ratio:
                mejor_ratio = ratio
                mejor = candidato
        return mejor if mejor_ratio >= 0.7 else None

    @staticmethod
    def _similaridad_simple(a: str, b: str) -> float:
        """Calcula una similitud liviana basada en tokens."""
        if not a or not b:
            return 0.0
        if a == b:
            return 1.0
        a_tokens = set(re.findall(r"\w+", a))
        b_tokens = set(re.findall(r"\w+", b))
        if not a_tokens or not b_tokens:
            return 0.0
        inter = len(a_tokens & b_tokens)
        union = len(a_tokens | b_tokens)
        return inter / union if union else 0.0

    def _generar_desde_perfil(self, perfil: dict, estructura: dict, tendencia: dict) -> dict:
        respuesta = {"paginas": []}
        respuestas_perfil = perfil.get("respuestas", {})

        for pagina in estructura.get("paginas", []):
            respuestas_pagina = []

            for pregunta in pagina.get("preguntas", []):
                texto = pregunta["texto"]
                tipo = pregunta["tipo"]
                opciones = pregunta.get("opciones", [])
                config_pregunta = self._buscar_config_pregunta(respuestas_perfil, texto)

                valor = None

                if tipo == "informativo":
                    continue
                elif config_pregunta:
                    valor = self._generar_segun_config(config_pregunta, opciones, pregunta_tipo=tipo)
                elif tipo in ("opcion_multiple", "seleccion_multiple") and opciones and self._es_likert(opciones):
                    # Likert disfrazado de opcion_multiple - usar tendencia
                    dist = self._obtener_distribucion(tendencia, len(opciones))
                    valor = random.choices(opciones, weights=dist)[0]
                elif tipo in ("opcion_multiple", "seleccion_multiple") and opciones:
                    valor = random.choice(opciones)
                elif tipo == "escala_lineal" and opciones:
                    dist = self._obtener_distribucion(tendencia, len(opciones))
                    valor = random.choices(opciones, weights=dist)[0]
                elif tipo == "numero":
                    if config_pregunta:
                        min_val = config_pregunta.get("min", 18)
                        max_val = config_pregunta.get("max", 60)
                    else:
                        min_val, max_val = 18, 60
                    valor = str(random.randint(min_val, max_val))
                elif tipo == "texto":
                    if config_pregunta and config_pregunta.get("valor"):
                        valor = config_pregunta["valor"]
                    elif config_pregunta and config_pregunta.get("opciones"):
                        items = list(config_pregunta["opciones"].keys())
                        pesos = list(config_pregunta["opciones"].values())
                        valor = random.choices(items, weights=pesos)[0] if items else self._inferir_texto(texto)
                    else:
                        valor = self._inferir_texto(texto)
                elif tipo == "desplegable" and opciones:
                    valor = random.choice(opciones)
                elif tipo == "fecha":
                    valor = f"2026-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
                elif tipo == "hora":
                    valor = f"{random.randint(6, 22):02d}:{random.choice(['00', '15', '30', '45'])}"

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

    @staticmethod
    def _es_likert(opciones: list) -> bool:
        """Detecta si opciones son tipo Likert (frecuencia/acuerdo)."""
        if len(opciones) < 3:
            return False
        opciones_lower = {o.lower().strip() for o in opciones}
        patrones = [
            {"nunca", "casi nunca", "a veces", "muchas veces", "siempre"},
            {"nunca", "raramente", "a veces", "frecuentemente", "siempre"},
            {"muy en desacuerdo", "en desacuerdo", "neutral", "de acuerdo", "muy de acuerdo"},
            {"totalmente en desacuerdo", "en desacuerdo", "ni de acuerdo ni en desacuerdo", "de acuerdo", "totalmente de acuerdo"},
            {"nada", "poco", "algo", "bastante", "mucho"},
            {"never", "rarely", "sometimes", "often", "always"},
        ]
        for patron in patrones:
            if len(opciones_lower & patron) >= 3:
                return True
        return False

    @staticmethod
    def _inferir_texto(texto: str) -> str:
        """Infiere un valor apropiado para campos de texto según el nombre de la pregunta."""
        t = texto.lower().strip()

        # Edad / Age
        if re.search(r'\bedad\b|\bage\b|\baños\b', t):
            return str(random.randint(20, 55))

        # DNI / Documento
        if re.search(r'\bdni\b|\bdocumento\b|\bcédula\b|\bcedula\b', t):
            return str(random.randint(10000000, 99999999))

        # Teléfono / Celular
        if re.search(r'\btel[eé]fono\b|\bcelular\b|\bmóvil\b|\bmovil\b|\bphone\b', t):
            return f"9{random.randint(10000000, 99999999)}"

        # Código postal
        if re.search(r'\bc[oó]digo postal\b|\bzip\b', t):
            return str(random.randint(10000, 99999))

        # Año / Year
        if re.search(r'\baño\b|\byear\b', t) and not re.search(r'años', t):
            return str(random.randint(2015, 2025))

        # Número genérico (si la pregunta pide un número)
        if re.search(r'\bn[uú]mero\b|\bcuántos\b|\bcuantos\b|\bcantidad\b', t):
            return str(random.randint(1, 20))

        # Email
        if re.search(r'\bemail\b|\bcorreo\b|\be-mail\b', t):
            return f"usuario{random.randint(100, 999)}@gmail.com"

        # Nombre
        if re.search(r'\bnombre completo\b|\bnombre y apellido\b|\bfull name\b', t):
            nombres = ["Juan Pérez", "María García", "Carlos López", "Ana Torres", "Luis Mendoza",
                        "Rosa Quispe", "Pedro Huamán", "Carmen Flores", "José Rojas", "Elena Vargas"]
            return random.choice(nombres)

        if re.search(r'\bnombre\b|\bname\b', t) and not re.search(r'número|apellido', t):
            nombres = ["Juan", "María", "Carlos", "Ana", "Luis", "Rosa", "Pedro", "Carmen", "José", "Elena"]
            return random.choice(nombres)

        return "respuesta"

    @staticmethod
    def _buscar_config_pregunta(respuestas_perfil: dict, texto: str):
        """Busca la configuración de una pregunta con exact match y prefix match."""
        def _norm(t: str) -> str:
            t = t.strip()
            # Quitar sufijos comunes de marcadores (*, ., espacios)
            t = t.rstrip("*. ").strip()
            return t

        def _norm_unicode(t: str) -> str:
            """Normaliza Unicode (NFKD), elimina tildes y signos de puntuación."""
            t = str(t or "").strip().lower()
            t = t.rstrip("*. :").strip()
            t = unicodedata.normalize("NFKD", t)
            t = "".join(ch for ch in t if not unicodedata.combining(ch))
            t = re.sub(r"[^\w\s]", " ", t)
            t = re.sub(r"\s+", " ", t).strip()
            return t

        # Exact match
        if texto in respuestas_perfil:
            return respuestas_perfil[texto]

        # Prefix match: "CASO 1:" matchea "CASO 1: Durante su servicio..."
        texto_lower = texto.lower().strip()
        for key, config in respuestas_perfil.items():
            key_lower = key.lower().strip()
            if not key_lower:
                continue
            if texto_lower.startswith(key_lower) or key_lower.startswith(texto_lower):
                return config

        # Match sin trailing spaces/asterisks/puntos
        texto_clean = _norm(texto)
        if texto_clean:
            for key, config in respuestas_perfil.items():
                key_clean = _norm(key)
                if key_clean and texto_clean == key_clean:
                    return config

        # Match con normalización Unicode NFKD (elimina diferencias de tildes/acentos)
        texto_uni = _norm_unicode(texto)
        if texto_uni:
            for key, config in respuestas_perfil.items():
                key_uni = _norm_unicode(key)
                if key_uni and (texto_uni == key_uni or texto_uni.startswith(key_uni) or key_uni.startswith(texto_uni)):
                    return config

        return None

    def _generar_segun_config(
        self,
        config: dict,
        opciones_disponibles: list,
        pregunta_tipo: str | None = None,
    ):
        tipo = config.get("tipo", "aleatorio")

        if tipo == "fijo":
            return config.get("valor", "")
        elif tipo == "rango":
            min_val = config.get("min", 0)
            max_val = config.get("max", 100)
            return str(random.randint(min_val, max_val))
        elif tipo == "aleatorio":
            opciones = config.get("opciones", {})
            if opciones:
                items = list(opciones.keys())
                pesos = list(opciones.values())
                return random.choices(items, weights=pesos)[0]
            elif opciones_disponibles:
                return random.choice(opciones_disponibles)
        elif tipo in ("multiple", "seleccion_multiple_condicionada"):
            # Selección múltiple ponderada: elige un patrón completo (lista de valores) según peso
            patrones = config.get("patrones", [])
            if isinstance(patrones, dict):
                claves = [k for k, v in patrones.items() if v and v > 0]
                pesos = [patrones[k] for k in claves]
                if claves:
                    elegido = random.choices(claves, weights=pesos)[0]
                    return self._resolver_patron_multiple(elegido, opciones_disponibles)
            elif isinstance(patrones, list) and patrones:
                validos = [p for p in patrones if p.get("peso", 0) > 0]
                if validos:
                    elegido = random.choices(validos, weights=[p.get("peso", 1) for p in validos])[0]
                    return self._resolver_patron_multiple(
                        elegido.get("valores", elegido.get("valor", [])),
                        opciones_disponibles,
                    )
            return []
        return [] if pregunta_tipo in ("seleccion_multiple", "matriz_checkbox") else ""

    def _resolver_patron_multiple(self, patron, opciones_disponibles: list) -> list[str]:
        """Convierte un patrÃ³n declarativo en una lista concreta de opciones."""
        if patron is None:
            return []

        if isinstance(patron, list):
            return [str(v).strip() for v in patron if str(v).strip()]

        if isinstance(patron, dict):
            valores = patron.get("valores", patron.get("valor"))
            return self._resolver_patron_multiple(valores, opciones_disponibles)

        texto = str(patron).strip()
        if not texto:
            return []

        texto_norm = self._normalize_rule_text(texto)
        if texto_norm in {"sin_dias", "sin_dia", "ninguno", "ninguna", "vacio", "vacia", "none", "empty"}:
            return []

        if "|" in texto or "," in texto:
            return [p.strip() for p in re.split(r"[|,]", texto) if p.strip()]

        matched = re.match(r"^(\d+)(?:\s*[_-]?\s*dias?)?$", texto_norm)
        if matched and opciones_disponibles:
            cantidad = min(int(matched.group(1)), len(opciones_disponibles))
            if cantidad <= 0:
                return []
            return random.sample(list(opciones_disponibles), cantidad)

        opcion = self._match_option(texto, opciones_disponibles)
        if opcion:
            return [opcion]

        return []

    def _obtener_distribucion(self, tendencia: dict, num_opciones: int) -> list:
        """Obtiene la distribución correcta para el tamaño de escala dado."""
        # Primero buscar en distribuciones específicas por tamaño
        distribuciones = tendencia.get("distribuciones", {})
        clave = str(num_opciones)
        if clave in distribuciones:
            return distribuciones[clave]

        # Fallback: usar distribución simple si existe
        distribucion = tendencia.get("distribucion", None)
        if distribucion:
            return self._ajustar_distribucion(distribucion, num_opciones)

        # Default: distribución uniforme
        return [1] * num_opciones

    def _ajustar_distribucion(self, distribucion: list, num_opciones: int) -> list:
        """Ajusta distribución proporcionalmente entre escalas diferentes (ej: 7→5 o 5→7)."""
        if len(distribucion) == num_opciones:
            return distribucion

        n_orig = len(distribucion)
        resultado = [0.0] * num_opciones

        for i in range(num_opciones):
            # Mapear posición i de la nueva escala al rango correspondiente en la original
            inicio = i * n_orig / num_opciones
            fin = (i + 1) * n_orig / num_opciones

            for j in range(n_orig):
                # Calcular cuánto del bucket j cae en el rango [inicio, fin]
                overlap_start = max(j, inicio)
                overlap_end = min(j + 1, fin)
                if overlap_end > overlap_start:
                    resultado[i] += distribucion[j] * (overlap_end - overlap_start)

        # Normalizar para que sume lo mismo que la original
        total_orig = sum(distribucion)
        total_nuevo = sum(resultado)
        if total_nuevo > 0:
            resultado = [r * total_orig / total_nuevo for r in resultado]

        return resultado

    def _aplicar_reglas(self, respuesta: dict, reglas: list) -> dict:
        if not reglas:
            return respuesta
        return self._aplicar_reglas_v2(respuesta, reglas)

        def _norm_q(texto: str) -> str:
            t = str(texto or "").strip()
            t = t.rstrip("*. :").strip()
            t = re.sub(r"\s+", " ", t).lower()
            # Normalización NFKD: elimina diferencias de tildes/acentos entre
            # el texto scrapeado y las claves del config JSON
            t = unicodedata.normalize("NFKD", t)
            t = "".join(ch for ch in t if not unicodedata.combining(ch))
            return t

        def _norm_val(valor) -> str:
            if valor is None:
                return ""
            return str(valor).strip()

        respuestas_planas = {}
        for pagina in respuesta.get("paginas", []):
            for r in pagina.get("respuestas", []):
                respuestas_planas[r["pregunta"]] = r["valor"]

        # Mapa normalizado de preguntas -> texto real en la respuesta
        norm_map = {}
        for pregunta in respuestas_planas.keys():
            clave = _norm_q(pregunta)
            if clave and clave not in norm_map:
                norm_map[clave] = pregunta

        cambios = {}
        for regla in reglas:
            si_pregunta = regla.get("si_pregunta", "")
            si_valor = regla.get("si_valor", "")
            operador = regla.get("operador", "igual")
            entonces_pregunta = regla.get("entonces_pregunta", "")
            excluir = regla.get("entonces_excluir", [])
            forzar = regla.get("entonces_forzar")

            si_key = norm_map.get(_norm_q(si_pregunta), si_pregunta)
            valor_actual = respuestas_planas.get(si_key, "")

            condicion_cumplida = False
            if operador == "igual":
                condicion_cumplida = _norm_val(valor_actual) == _norm_val(si_valor)
            elif operador == "diferente":
                condicion_cumplida = _norm_val(valor_actual) != _norm_val(si_valor)
            elif operador == "menor":
                try:
                    condicion_cumplida = float(valor_actual) < float(si_valor)
                except ValueError:
                    pass
            elif operador == "mayor":
                try:
                    condicion_cumplida = float(valor_actual) > float(si_valor)
                except ValueError:
                    pass

            if condicion_cumplida:
                ent_key = norm_map.get(_norm_q(entonces_pregunta), entonces_pregunta)
                if forzar is not None and str(forzar).strip() != "":
                    cambios[ent_key] = self._resolver_forzar(forzar)
                elif excluir:
                    valor_entonces = respuestas_planas.get(ent_key, "")
                    if valor_entonces in excluir:
                        for pagina in respuesta.get("paginas", []):
                            for r in pagina.get("respuestas", []):
                                if r["pregunta"] == ent_key:
                                    opciones_validas = [
                                        o for o in r.get("opciones_disponibles", [])
                                        if o not in excluir
                                    ]
                                    if opciones_validas:
                                        cambios[ent_key] = random.choice(opciones_validas)

        # Mapa normalizado de cambios para aplicación robusta ante diferencias Unicode
        cambios_norm = {_norm_q(k): v for k, v in cambios.items()}

        for pagina in respuesta.get("paginas", []):
            for r in pagina.get("respuestas", []):
                if r["pregunta"] in cambios:
                    r["valor"] = cambios[r["pregunta"]]
                else:
                    # Fallback: buscar por clave normalizada (NFKD)
                    r_norm = _norm_q(r["pregunta"])
                    if r_norm in cambios_norm:
                        r["valor"] = cambios_norm[r_norm]

        return respuesta

    def _resolver_forzar(self, forzar):
        """Resuelve valores forzados (soporta rangos y listas)."""
        if isinstance(forzar, list):
            return [str(v).strip() for v in forzar if str(v).strip()]

        if isinstance(forzar, (int, float)):
            return str(int(forzar)) if isinstance(forzar, bool) is False and float(forzar).is_integer() else str(forzar)

        if isinstance(forzar, str):
            texto = forzar.strip()
            if not texto:
                return ""
            # Normalizar guiones
            texto_norm = texto.replace("–", "-").replace("—", "-")
            # Rango numérico: "14-15"
            m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", texto_norm)
            if m:
                a = int(m.group(1))
                b = int(m.group(2))
                if a > b:
                    a, b = b, a
                return str(random.randint(a, b))
            # Lista por separador: "14,15" o "14|15"
            if "|" in texto_norm or "," in texto_norm:
                partes = [p.strip() for p in re.split(r"[|,]", texto_norm) if p.strip()]
                if partes:
                    return str(random.choice(partes))
            return texto

        return str(forzar)

    def _aplicar_reglas_v2(self, respuesta: dict, reglas: list) -> dict:
        respuestas_planas = {}
        respuestas_meta = {}
        for pagina in respuesta.get("paginas", []):
            for r in pagina.get("respuestas", []):
                respuestas_planas[r["pregunta"]] = r["valor"]
                respuestas_meta[r["pregunta"]] = r

        norm_map = {}
        for pregunta in respuestas_planas.keys():
            clave = self._normalize_rule_text(pregunta)
            if clave and clave not in norm_map:
                norm_map[clave] = pregunta

        cambios = {}
        for regla in reglas:
            si_pregunta = regla.get("si_pregunta", "")
            si_valor = regla.get("si_valor", "")
            operador = regla.get("operador", "igual")
            entonces_pregunta = regla.get("entonces_pregunta", "")
            excluir = regla.get("entonces_excluir", [])
            forzar = regla.get("entonces_forzar")
            permitir = regla.get("entonces_permitir", [])

            si_key = norm_map.get(self._normalize_rule_text(si_pregunta), si_pregunta)
            valor_actual = cambios.get(si_key, respuestas_planas.get(si_key, ""))
            if not self._evaluar_condicion_regla(valor_actual, operador, si_valor):
                continue

            ent_key = norm_map.get(self._normalize_rule_text(entonces_pregunta), entonces_pregunta)
            valor_entonces = cambios.get(ent_key, respuestas_planas.get(ent_key, ""))
            opciones_disponibles = respuestas_meta.get(ent_key, {}).get("opciones_disponibles", [])

            if forzar is not None:
                nuevo_valor = self._resolver_forzar(forzar)
            elif excluir or permitir:
                nuevo_valor = self._aplicar_restricciones_a_valor(
                    valor_entonces,
                    opciones_disponibles,
                    excluir=excluir,
                    permitir=permitir,
                )
            else:
                continue

            cambios[ent_key] = nuevo_valor
            respuestas_planas[ent_key] = nuevo_valor

        cambios_norm = {self._normalize_rule_text(k): v for k, v in cambios.items()}
        for pagina in respuesta.get("paginas", []):
            for r in pagina.get("respuestas", []):
                if r["pregunta"] in cambios:
                    r["valor"] = cambios[r["pregunta"]]
                    continue
                r_norm = self._normalize_rule_text(r["pregunta"])
                if r_norm in cambios_norm:
                    r["valor"] = cambios_norm[r_norm]

        return respuesta

    @staticmethod
    def _normalize_rule_text(texto: str) -> str:
        return _norm_text(texto or "")

    def _match_option(self, texto: str, opciones_disponibles: list) -> str | None:
        target = self._normalize_rule_text(texto)
        for opcion in opciones_disponibles:
            if self._normalize_rule_text(opcion) == target:
                return opcion
        for opcion in opciones_disponibles:
            opcion_norm = self._normalize_rule_text(opcion)
            if target and opcion_norm and (target in opcion_norm or opcion_norm in target):
                return opcion
        return None

    def _evaluar_condicion_regla(self, valor_actual, operador: str, si_valor) -> bool:
        operador = str(operador or "igual").strip().lower()

        if operador == "igual":
            return self._valores_equivalentes(valor_actual, si_valor)
        if operador == "diferente":
            return not self._valores_equivalentes(valor_actual, si_valor)
        if operador == "cardinalidad_igual":
            try:
                return len(self._as_clean_list(valor_actual)) == int(si_valor)
            except (TypeError, ValueError):
                return False
        if operador == "cardinalidad_mayor":
            try:
                return len(self._as_clean_list(valor_actual)) > int(si_valor)
            except (TypeError, ValueError):
                return False
        if operador == "cardinalidad_menor":
            try:
                return len(self._as_clean_list(valor_actual)) < int(si_valor)
            except (TypeError, ValueError):
                return False
        if operador == "contiene":
            return self._valor_contiene(valor_actual, si_valor)
        if operador == "no_contiene":
            return not self._valor_contiene(valor_actual, si_valor)
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

    def _valores_equivalentes(self, a, b) -> bool:
        if isinstance(a, list) or isinstance(b, list):
            a_norm = sorted(self._normalize_rule_text(v) for v in self._as_clean_list(a))
            b_norm = sorted(self._normalize_rule_text(v) for v in self._as_clean_list(b))
            return a_norm == b_norm
        return self._normalize_rule_text(a) == self._normalize_rule_text(b)

    def _valor_contiene(self, valor_actual, esperado) -> bool:
        esperado_norm = self._normalize_rule_text(esperado)
        if not esperado_norm:
            return False
        if isinstance(valor_actual, list):
            return esperado_norm in [self._normalize_rule_text(v) for v in self._as_clean_list(valor_actual)]
        return esperado_norm in self._normalize_rule_text(valor_actual)

    def _aplicar_restricciones_a_valor(
        self,
        valor_actual,
        opciones_disponibles: list,
        excluir: list | None = None,
        permitir: list | None = None,
    ):
        excluir = excluir or []
        permitir = permitir or []

        opciones_validas = []
        vistos = set()
        excluir_norm = {self._normalize_rule_text(v) for v in excluir if str(v).strip()}
        permitir_norm = {self._normalize_rule_text(v) for v in permitir if str(v).strip()}

        for opcion in opciones_disponibles:
            opcion_norm = self._normalize_rule_text(opcion)
            if not opcion_norm or opcion_norm in vistos:
                continue
            if excluir_norm and opcion_norm in excluir_norm:
                continue
            if permitir_norm and opcion_norm not in permitir_norm:
                continue
            opciones_validas.append(opcion)
            vistos.add(opcion_norm)

        if isinstance(valor_actual, list):
            actual = self._as_clean_list(valor_actual)
            target_len = len(actual)
            filtrados = []
            usados = set()
            validas_norm = {self._normalize_rule_text(v) for v in opciones_validas}
            for item in actual:
                item_norm = self._normalize_rule_text(item)
                if item_norm in validas_norm and item_norm not in usados:
                    filtrados.append(item)
                    usados.add(item_norm)

            faltantes = max(0, target_len - len(filtrados))
            candidatos = [v for v in opciones_validas if self._normalize_rule_text(v) not in usados]
            if faltantes > 0 and candidatos:
                random.shuffle(candidatos)
                filtrados.extend(candidatos[:faltantes])
            return filtrados

        actual_norm = self._normalize_rule_text(valor_actual)
        if actual_norm and actual_norm in {self._normalize_rule_text(v) for v in opciones_validas}:
            return valor_actual
        if opciones_validas:
            return random.choice(opciones_validas)
        return valor_actual

    @staticmethod
    def _as_clean_list(valor) -> list[str]:
        if isinstance(valor, list):
            return [str(v).strip() for v in valor if str(v).strip()]
        if valor is None:
            return []
        texto = str(valor).strip()
        return [texto] if texto else []

    def _garantizar_respuestas_obligatorias(self, respuesta: dict, estructura: dict) -> dict:
        """Evita respuestas vacÃ­as en selecciones mÃºltiples obligatorias."""
        preguntas_por_clave = {}
        for pagina in estructura.get("paginas", []):
            for pregunta in pagina.get("preguntas", []):
                clave = self._normalize_rule_text(pregunta.get("texto", ""))
                if clave:
                    preguntas_por_clave[clave] = pregunta

        for pagina in respuesta.get("paginas", []):
            for r in pagina.get("respuestas", []):
                pregunta = preguntas_por_clave.get(self._normalize_rule_text(r.get("pregunta", "")), {})
                if pregunta.get("tipo") != "seleccion_multiple" or not pregunta.get("obligatoria"):
                    continue
                if self._as_clean_list(r.get("valor")):
                    continue
                opciones = r.get("opciones_disponibles") or pregunta.get("opciones") or []
                if opciones:
                    r["valor"] = [random.choice(opciones)]

        return respuesta
