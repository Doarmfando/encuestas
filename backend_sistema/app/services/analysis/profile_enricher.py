"""
Enriquecimiento de perfiles con tendencia sugerida y reglas de coherencia.
Solo responsabilidad: completar metadatos de coherencia en cada perfil.
Para agregar un nuevo tipo de regla de coherencia: solo editar este archivo.
"""
from app.utils.fuzzy_matcher import find_best_match


_PATRONES_TENDENCIA = [
    (
        ("alto", "positivo", "resiliente", "adaptado", "optimista", "estable", "funcional"),
        ("alto", "arriba", "positivo", "superior", "favorable"),
    ),
    (
        ("bajo", "critico", "crítico", "vulnerable", "riesgo", "negativo", "estres", "estrés"),
        ("bajo", "abajo", "negativo", "critico", "crítico", "desfavorable"),
    ),
    (
        ("medio", "moderado", "neutro", "promedio", "equilibrado"),
        ("medio", "centro", "neutro", "moderado", "promedio"),
    ),
]

_MAX_REGLAS_COHERENCIA = 5


class ProfileEnricher:
    """Completa metadatos de cada perfil para que el generador pueda usarlos.

    Para agregar un nuevo campo de coherencia (ej. 'zona geográfica'),
    agregar la detección en _generar_reglas_coherencia sin tocar otros archivos.
    """

    def enriquecer(self, perfiles: list, ref_map: dict, tendencias: list):
        """Completa tendencia_sugerida, tendencias_preferidas y reglas_coherencia."""
        nombres_tendencia = [t.get("nombre", "") for t in tendencias if t.get("nombre")]
        for perfil in perfiles:
            preferidas = self._normalizar_tendencias_preferidas(
                perfil.get("tendencias_preferidas"), nombres_tendencia
            )
            if preferidas:
                perfil["tendencias_preferidas"] = preferidas
            else:
                perfil.pop("tendencias_preferidas", None)

            perfil["tendencia_sugerida"] = self._resolver_tendencia_sugerida(
                perfil, nombres_tendencia, preferidas
            )
            perfil["reglas_coherencia"] = self._generar_reglas_coherencia(
                perfil,
                perfil.get("reglas_coherencia"),
                perfil["tendencia_sugerida"],
            )

    # ── privados ──────────────────────────────────────────────────────────────

    def _resolver_tendencia_sugerida(
        self, perfil: dict, nombres: list, preferidas: dict | None
    ) -> str | None:
        if not nombres:
            return None

        sugerida = find_best_match(perfil.get("tendencia_sugerida") or "", nombres, threshold=0.7)
        if sugerida:
            return sugerida

        if preferidas:
            return max(preferidas.items(), key=lambda item: item[1])[0]

        texto = f"{perfil.get('nombre', '')} {perfil.get('descripcion', '')}".lower()
        for claves_perfil, claves_tendencia in _PATRONES_TENDENCIA:
            if any(token in texto for token in claves_perfil):
                for nombre in nombres:
                    if any(token in nombre.lower() for token in claves_tendencia):
                        return nombre

        for nombre in nombres:
            if any(token in nombre.lower() for token in ("medio", "centro", "neutro", "moderado")):
                return nombre

        return nombres[0]

    def _normalizar_tendencias_preferidas(self, valor, nombres: list) -> dict:
        if not valor or not nombres:
            return {}

        normalizado: dict = {}
        if isinstance(valor, dict):
            for nombre, peso in valor.items():
                match = find_best_match(nombre, nombres, threshold=0.7)
                if not match:
                    continue
                try:
                    normalizado[match] = normalizado.get(match, 0) + max(1, int(peso))
                except Exception:
                    normalizado[match] = normalizado.get(match, 0) + 1
        elif isinstance(valor, list):
            peso = round(100 / max(len(valor), 1))
            for nombre in valor:
                match = find_best_match(nombre, nombres, threshold=0.7)
                if match:
                    normalizado[match] = normalizado.get(match, 0) + peso

        if not normalizado:
            return {}
        total = sum(normalizado.values())
        if total <= 0:
            return {}
        return {k: max(1, round(v * 100 / total)) for k, v in normalizado.items()}

    def _generar_reglas_coherencia(
        self, perfil: dict, reglas_existentes, tendencia_sugerida: str | None
    ) -> list:
        reglas: list = []
        if isinstance(reglas_existentes, list):
            reglas = [str(r).strip() for r in reglas_existentes if str(r).strip()]

        respuestas = perfil.get("respuestas", {})
        edad = self._buscar_respuesta(respuestas, ("edad", "age"))
        sexo = self._buscar_respuesta(respuestas, ("sexo", "género", "genero", "gender"))
        estado_civil = self._buscar_respuesta(respuestas, ("estado civil", "civil"))
        instruccion = self._buscar_respuesta(
            respuestas, ("grado de instrucción", "grado de instruccion", "instrucción", "instruccion", "educación", "educacion")
        )
        ocupacion = self._buscar_respuesta(respuestas, ("ocupación", "ocupacion", "trabaja", "estudia"))
        convivencia = self._buscar_respuesta(respuestas, ("vive", "convive", "con quien vive"))
        hijos = self._buscar_respuesta(respuestas, ("hijos", "hijo", "hija"))

        nuevas: list = []
        if edad:
            nuevas.append(f"Edad base del perfil: {edad}. Mantener respuestas compatibles con ese rango etario.")
        if sexo:
            nuevas.append(f"Sexo o género dominante del perfil: {sexo}. Evitar contradicciones con preguntas derivadas.")
        if estado_civil and convivencia:
            nuevas.append(f"Estado civil y convivencia deben ser consistentes: {estado_civil} / {convivencia}.")
        elif estado_civil:
            nuevas.append(f"El estado civil dominante es {estado_civil}; evitar combinaciones improbables.")
        if instruccion and ocupacion:
            nuevas.append(f"Ocupación e instrucción deben ir juntas: {ocupacion} con {instruccion}.")
        elif ocupacion:
            nuevas.append(f"La ocupación principal es {ocupacion}; mantener consistencia con edad y contexto.")
        if hijos:
            if any(token in hijos.lower() for token in ("no", "ninguno", "0")):
                nuevas.append("Si el perfil no tiene hijos, usar 0 o no aplica en preguntas sobre hijos.")
            else:
                nuevas.append("Si el perfil tiene hijos, mantener consistencia en cantidad y convivencia.")
        if tendencia_sugerida:
            nuevas.append(f"Para preguntas de escala, inclinarse hacia la tendencia '{tendencia_sugerida}'.")

        nuevas.append("Las respuestas sensibles deben seguir la misma narrativa del perfil.")

        todas = reglas + [r for r in nuevas if r not in reglas]
        return [r for r in dict.fromkeys(todas) if r][:_MAX_REGLAS_COHERENCIA]

    def _buscar_respuesta(self, respuestas: dict, keywords: tuple) -> str | None:
        for pregunta, config in respuestas.items():
            if any(kw in pregunta.lower() for kw in keywords):
                return self._resumen_config(config)
        return None

    def _resumen_config(self, config: dict) -> str:
        if not isinstance(config, dict):
            return str(config)
        tipo = config.get("tipo")
        if tipo == "fijo":
            return str(config.get("valor", ""))
        if tipo == "rango":
            return f"{config.get('min', '?')}-{config.get('max', '?')}"
        if tipo == "aleatorio":
            opciones = config.get("opciones", {})
            if isinstance(opciones, dict) and opciones:
                return str(max(opciones.items(), key=lambda item: item[1])[0])
        return ""
