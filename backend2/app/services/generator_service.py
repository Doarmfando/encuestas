"""
Servicio de generación de respuestas basado en perfiles + reglas + tendencias.
"""
import random
import re


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
                    valor = self._generar_segun_config(config_pregunta, opciones)
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
        # Exact match
        if texto in respuestas_perfil:
            return respuestas_perfil[texto]

        # Prefix match: "CASO 1:" matchea "CASO 1: Durante su servicio..."
        texto_lower = texto.lower().strip()
        for key, config in respuestas_perfil.items():
            key_lower = key.lower().strip()
            if texto_lower.startswith(key_lower) or key_lower.startswith(texto_lower):
                return config

        # Match sin trailing spaces/asterisks
        texto_clean = texto.strip().rstrip("*").strip()
        for key, config in respuestas_perfil.items():
            key_clean = key.strip().rstrip("*").strip()
            if texto_clean == key_clean:
                return config

        return None

    def _generar_segun_config(self, config: dict, opciones_disponibles: list):
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
        return ""

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

        respuestas_planas = {}
        for pagina in respuesta.get("paginas", []):
            for r in pagina.get("respuestas", []):
                respuestas_planas[r["pregunta"]] = r["valor"]

        cambios = {}
        for regla in reglas:
            si_pregunta = regla.get("si_pregunta", "")
            si_valor = regla.get("si_valor", "")
            operador = regla.get("operador", "igual")
            entonces_pregunta = regla.get("entonces_pregunta", "")
            excluir = regla.get("entonces_excluir", [])
            forzar = regla.get("entonces_forzar")

            valor_actual = respuestas_planas.get(si_pregunta, "")

            condicion_cumplida = False
            if operador == "igual":
                condicion_cumplida = valor_actual == si_valor
            elif operador == "diferente":
                condicion_cumplida = valor_actual != si_valor
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
                if forzar:
                    cambios[entonces_pregunta] = forzar
                elif excluir:
                    valor_entonces = respuestas_planas.get(entonces_pregunta, "")
                    if valor_entonces in excluir:
                        for pagina in respuesta.get("paginas", []):
                            for r in pagina.get("respuestas", []):
                                if r["pregunta"] == entonces_pregunta:
                                    opciones_validas = [
                                        o for o in r.get("opciones_disponibles", [])
                                        if o not in excluir
                                    ]
                                    if opciones_validas:
                                        cambios[entonces_pregunta] = random.choice(opciones_validas)

        for pagina in respuesta.get("paginas", []):
            for r in pagina.get("respuestas", []):
                if r["pregunta"] in cambios:
                    r["valor"] = cambios[r["pregunta"]]

        return respuesta
