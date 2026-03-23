"""
Generador de respuestas basado en perfiles + reglas + tendencias.
Recibe la configuración (de GPT o editada por el usuario) y genera respuestas coherentes.
"""
import random


def generar_respuesta(configuracion, estructura_encuesta):
    """Genera una respuesta completa para el formulario."""

    perfiles = configuracion.get("perfiles", [])
    reglas = configuracion.get("reglas_dependencia", [])
    tendencias = configuracion.get("tendencias_escalas", [])

    # 1. Elegir perfil según frecuencias
    perfil = _elegir_perfil(perfiles)

    # 2. Elegir tendencia para escalas
    tendencia = _elegir_tendencia(tendencias)

    # 3. Generar respuestas base según el perfil
    respuesta = _generar_desde_perfil(perfil, estructura_encuesta, tendencia)

    # 4. Aplicar reglas de dependencia
    respuesta = _aplicar_reglas(respuesta, reglas)

    # 5. Agregar metadata
    respuesta["_perfil"] = perfil.get("nombre", "desconocido")
    respuesta["_tendencia"] = tendencia.get("nombre", "desconocido")

    return respuesta


def _elegir_perfil(perfiles):
    """Elige un perfil según las frecuencias/pesos."""
    if not perfiles:
        return {"nombre": "default", "respuestas": {}, "frecuencia": 100}

    nombres = [p["nombre"] for p in perfiles]
    pesos = [p.get("frecuencia", 10) for p in perfiles]
    elegido = random.choices(perfiles, weights=pesos)[0]
    return elegido


def _elegir_tendencia(tendencias):
    """Elige una tendencia de respuesta para las escalas."""
    if not tendencias:
        return {
            "nombre": "neutro",
            "distribucion": [20, 20, 20, 20, 20],
            "frecuencia": 100,
        }

    pesos = [t.get("frecuencia", 10) for t in tendencias]
    elegida = random.choices(tendencias, weights=pesos)[0]
    return elegida


def _generar_desde_perfil(perfil, estructura, tendencia):
    """Genera respuestas para cada pregunta según el perfil y tendencia."""
    respuesta = {"paginas": []}
    respuestas_perfil = perfil.get("respuestas", {})

    for pagina in estructura.get("paginas", []):
        respuestas_pagina = []

        for pregunta in pagina.get("preguntas", []):
            texto = pregunta["texto"]
            tipo = pregunta["tipo"]
            opciones = pregunta.get("opciones", [])
            filas = pregunta.get("filas", [])

            # Tipos que se saltan
            if tipo in ("informativo", "imagen", "archivo"):
                continue

            # No llenar si está marcado
            if pregunta.get("no_llenar"):
                continue

            # Buscar si el perfil tiene config para esta pregunta
            config_pregunta = respuestas_perfil.get(texto, None)

            valor = None

            if config_pregunta:
                valor = _generar_segun_config(config_pregunta, opciones)

            elif tipo in ("opcion_multiple", "seleccion_multiple") and opciones:
                # Filtrar "Otro" a menos que no haya más opciones
                opciones_sin_otro = [o for o in opciones if o != "Otro"]
                pool = opciones_sin_otro if opciones_sin_otro else opciones
                if tipo == "seleccion_multiple":
                    # Seleccionar 1 a 3 opciones
                    n = min(random.randint(1, 3), len(pool))
                    valor = random.sample(pool, n)
                else:
                    valor = random.choice(pool)

            elif tipo in ("escala_lineal", "nps") and opciones:
                # Usar la tendencia con distribuciones por tamaño de escala
                num_opts = len(opciones)
                distribuciones = tendencia.get("distribuciones", {})
                distribucion = distribuciones.get(str(num_opts), tendencia.get("distribucion", []))
                if not distribucion:
                    distribucion = [100 // num_opts] * num_opts
                dist = _ajustar_distribucion(distribucion, num_opts)
                valor = random.choices(opciones, weights=dist)[0]

            elif tipo in ("likert", "matriz", "matriz_checkbox"):
                # Generar respuesta para cada fila de la matriz
                valor = _generar_matriz(filas, opciones, tendencia, tipo)

            elif tipo == "ranking" and opciones:
                # Ranking: devolver opciones en orden aleatorio
                valor = opciones.copy()
                random.shuffle(valor)

            elif tipo == "numero":
                min_val, max_val = 18, 60
                validacion = pregunta.get("validacion", {})
                if validacion:
                    min_val = validacion.get("min", min_val) or min_val
                    max_val = validacion.get("max", max_val) or max_val
                valor = str(random.randint(int(min_val), int(max_val)))

            elif tipo == "texto":
                valor = ""

            elif tipo == "parrafo":
                valor = ""

            elif tipo == "desplegable" and opciones:
                valor = random.choice(opciones)

            elif tipo == "fecha":
                valor = f"2026-{random.randint(1,12):02d}-{random.randint(1,28):02d}"

            elif tipo == "hora":
                valor = f"{random.randint(6,22):02d}:{random.choice(['00','15','30','45'])}"

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


def _generar_matriz(filas, opciones, tendencia, tipo):
    """Genera respuestas para una pregunta tipo matriz/grid.

    Returns:
        dict: {"fila1": "opcion_elegida", "fila2": "opcion_elegida", ...}
        Para matriz_checkbox: {"fila1": ["opt1", "opt2"], ...}
    """
    resultado = {}

    if not filas:
        # Si no hay filas definidas, generar como lista
        return random.choice(opciones) if opciones else ""

    distribuciones = tendencia.get("distribuciones", {})
    num_opts = len(opciones)
    distribucion = distribuciones.get(str(num_opts), tendencia.get("distribucion", []))
    if not distribucion or len(distribucion) == 0:
        distribucion = [100 // max(num_opts, 1)] * max(num_opts, 1)
    dist = _ajustar_distribucion(distribucion, num_opts)

    for fila in filas:
        if tipo == "matriz_checkbox" and opciones:
            # Seleccionar 1-2 opciones por fila
            n = min(random.randint(1, 2), len(opciones))
            resultado[fila] = random.sample(opciones, n)
        elif opciones:
            resultado[fila] = random.choices(opciones, weights=dist)[0]
        else:
            resultado[fila] = ""

    return resultado


def _generar_segun_config(config, opciones_disponibles):
    """Genera un valor según la configuración del perfil."""
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


def _ajustar_distribucion(distribucion, num_opciones):
    """Ajusta la distribución al número real de opciones."""
    if len(distribucion) == num_opciones:
        return distribucion

    if len(distribucion) > num_opciones:
        return distribucion[:num_opciones]

    # Si hay más opciones que distribución, interpolar
    resultado = []
    ratio = len(distribucion) / num_opciones
    for i in range(num_opciones):
        idx = min(int(i * ratio), len(distribucion) - 1)
        resultado.append(distribucion[idx])

    return resultado


def _aplicar_reglas(respuesta, reglas):
    """Aplica reglas de dependencia a las respuestas generadas."""
    if not reglas:
        return respuesta

    # Recopilar todas las respuestas en un dict plano para evaluar
    respuestas_planas = {}
    for pagina in respuesta.get("paginas", []):
        for r in pagina.get("respuestas", []):
            respuestas_planas[r["pregunta"]] = r["valor"]

    # Evaluar cada regla
    cambios = {}
    for regla in reglas:
        si_pregunta = regla.get("si_pregunta", "")
        si_valor = regla.get("si_valor", "")
        operador = regla.get("operador", "igual")
        entonces_pregunta = regla.get("entonces_pregunta", "")
        excluir = regla.get("entonces_excluir", [])
        forzar = regla.get("entonces_forzar")

        valor_actual = respuestas_planas.get(si_pregunta, "")

        # Evaluar condición
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
                    # Buscar opciones disponibles que no estén excluidas
                    for pagina in respuesta.get("paginas", []):
                        for r in pagina.get("respuestas", []):
                            if r["pregunta"] == entonces_pregunta:
                                opciones_validas = [o for o in r.get("opciones_disponibles", []) if o not in excluir]
                                if opciones_validas:
                                    cambios[entonces_pregunta] = random.choice(opciones_validas)

    # Aplicar cambios
    for pagina in respuesta.get("paginas", []):
        for r in pagina.get("respuestas", []):
            if r["pregunta"] in cambios:
                r["valor"] = cambios[r["pregunta"]]

    return respuesta
