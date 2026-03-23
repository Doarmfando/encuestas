"""
Servicio de análisis de encuestas con IA.
Valida cruzando la respuesta de la IA contra la estructura real del formulario.
"""
import json
from difflib import SequenceMatcher
from app.ai.prompts import PROMPT_SISTEMA_ANALISIS, PROMPT_ANALISIS_ENCUESTA
from app.services.ai_service import AIService
from app.database.models import PromptTemplate


class AnalyzerService:
    """Analiza encuestas con IA para generar perfiles, reglas y tendencias."""

    def __init__(self, ai_service: AIService):
        self.ai = ai_service

    def analyze(self, estructura_scrapeada: dict, instrucciones_extra: str = "") -> dict:
        """Analiza la estructura y genera configuración de perfiles."""
        resumen = self._preparar_resumen(estructura_scrapeada)
        preguntas_ref = self._extraer_preguntas_referencia(estructura_scrapeada)

        print("  Enviando a IA para análisis...")

        try:
            # Leer prompts de BD (personalizados) o usar hardcoded como fallback
            system_prompt = PROMPT_SISTEMA_ANALISIS
            user_prompt_tpl = PROMPT_ANALISIS_ENCUESTA
            try:
                p_sys = PromptTemplate.query.filter_by(slug="system_analysis").first()
                if p_sys:
                    system_prompt = p_sys.contenido
                p_usr = PromptTemplate.query.filter_by(slug="user_analysis").first()
                if p_usr:
                    user_prompt_tpl = p_usr.contenido
            except Exception:
                pass

            provider = self.ai.get_provider()
            # Contar preguntas NO-escala para dimensionar tokens
            num_preguntas = len(resumen.get("preguntas", []))
            max_tokens = max(6000, min(16000, num_preguntas * 300))
            print(f"  Preguntas para perfiles: {num_preguntas}, max_tokens: {max_tokens}")

            user_prompt = user_prompt_tpl.format(
                encuesta_json=json.dumps(resumen, ensure_ascii=False, indent=2)
            )
            if instrucciones_extra:
                user_prompt += f"\n\n═══════════════════════════════════════\nINSTRUCCIONES ADICIONALES DEL USUARIO:\n═══════════════════════════════════════\n{instrucciones_extra}\n"

            contenido = provider.chat_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.7,
                max_tokens=max_tokens,
                json_mode=True,
            )

            resultado = json.loads(contenido)

            # Validación cruzada contra la estructura real
            resultado = self._validar_contra_estructura(resultado, preguntas_ref)

            print(f"  IA generó:")
            print(f"    {len(resultado.get('perfiles', []))} perfiles")
            print(f"    {len(resultado.get('reglas_dependencia', []))} reglas")
            print(f"    {len(resultado.get('tendencias_escalas', []))} tendencias")

            return resultado

        except Exception as e:
            print(f"  Error con IA: {e}")
            return self._generar_fallback(estructura_scrapeada)

    # ========== PREPARACIÓN ==========

    def _preparar_resumen(self, estructura: dict) -> dict:
        """Prepara un resumen compacto para enviar a la IA."""
        resumen = {
            "titulo": estructura.get("titulo", ""),
            "descripcion": estructura.get("descripcion", ""),
            "preguntas": [],
            "preguntas_escala_likert": [],
        }

        # Detectar opciones Likert repetidas para agrupar
        opciones_likert_vistas = set()

        for pagina in estructura.get("paginas", []):
            for pregunta in pagina.get("preguntas", []):
                tipo = pregunta.get("tipo", "")
                opciones = pregunta.get("opciones", [])
                if tipo in ("informativo", "desconocido", ""):
                    continue

                # Detectar Likert disfrazado
                if self._es_escala(tipo, opciones):
                    opts_key = tuple(sorted(o.lower() for o in opciones))
                    if opts_key not in opciones_likert_vistas:
                        opciones_likert_vistas.add(opts_key)
                    resumen["preguntas_escala_likert"].append({
                        "texto": pregunta["texto"],
                        "opciones": opciones,
                    })
                    continue

                entry = {
                    "texto": pregunta["texto"],
                    "tipo": tipo,
                    "obligatoria": pregunta.get("obligatoria", False),
                }
                # Solo incluir opciones si son pocas (no inflar el resumen)
                if opciones and len(opciones) <= 10:
                    entry["opciones"] = opciones
                elif opciones:
                    entry["opciones"] = opciones[:5] + [f"... (+{len(opciones)-5} más)"]
                resumen["preguntas"].append(entry)

        # Resumen de escalas
        if resumen["preguntas_escala_likert"]:
            escalas = resumen["preguntas_escala_likert"]
            # Agrupar por opciones para comprimir
            primer_ejemplo = escalas[0]
            resumen["nota_escalas"] = (
                f"Hay {len(escalas)} preguntas de escala/Likert con opciones como "
                f"{primer_ejemplo['opciones']}. NO las incluyas en perfiles, "
                f"van en tendencias_escalas. Ejemplos: {', '.join(e['texto'][:40] for e in escalas[:3])}"
            )
            del resumen["preguntas_escala_likert"]

        return resumen

    def _extraer_preguntas_referencia(self, estructura: dict) -> list:
        """Extrae lista de preguntas con su tipo y opciones como referencia."""
        preguntas = []
        for pagina in estructura.get("paginas", []):
            for pregunta in pagina.get("preguntas", []):
                tipo = pregunta.get("tipo", "")
                if tipo in ("informativo", "desconocido", ""):
                    continue
                preguntas.append({
                    "texto": pregunta["texto"],
                    "tipo": tipo,
                    "opciones": pregunta.get("opciones", []),
                    "obligatoria": pregunta.get("obligatoria", False),
                })
        return preguntas

    # ========== VALIDACIÓN CRUZADA ==========

    def _validar_contra_estructura(self, resultado: dict, preguntas_ref: list) -> dict:
        """Valida y corrige el resultado de la IA contra la estructura real."""
        if "perfiles" not in resultado:
            resultado["perfiles"] = []
        if "reglas_dependencia" not in resultado:
            resultado["reglas_dependencia"] = []
        if "tendencias_escalas" not in resultado:
            resultado["tendencias_escalas"] = []

        # Construir mapa de referencia
        ref_map = {}
        tiene_escalas = False
        tamaños_escala = set()

        for p in preguntas_ref:
            ref_map[p["texto"]] = p
            if self._es_escala(p["tipo"], p.get("opciones", [])):
                tiene_escalas = True
                n = len(p.get("opciones", []))
                if n > 0:
                    tamaños_escala.add(n)

        # Corregir cada perfil
        for perfil in resultado["perfiles"]:
            if "respuestas" not in perfil:
                perfil["respuestas"] = {}

            # 1. Corregir nombres de preguntas (fuzzy match)
            perfil["respuestas"] = self._corregir_nombres_preguntas(
                perfil["respuestas"], ref_map
            )

            # 2. Corregir cada respuesta según el tipo real
            for texto_pregunta, config in list(perfil["respuestas"].items()):
                ref = ref_map.get(texto_pregunta)
                perfil["respuestas"][texto_pregunta] = self._corregir_respuesta(
                    config, ref
                )

            # 3. Agregar preguntas faltantes
            for ref_preg in preguntas_ref:
                texto = ref_preg["texto"]
                if texto not in perfil["respuestas"] and not self._es_escala(ref_preg["tipo"], ref_preg.get("opciones", [])):
                    perfil["respuestas"][texto] = self._generar_respuesta_default(ref_preg)
                    print(f"    [+] Agregada pregunta faltante: {texto[:40]}...")

            # 4. Eliminar preguntas de escala de los perfiles (van en tendencias)
            for texto_pregunta in list(perfil["respuestas"].keys()):
                ref = ref_map.get(texto_pregunta)
                if ref and self._es_escala(ref["tipo"], ref.get("opciones", [])):
                    del perfil["respuestas"][texto_pregunta]

        # Normalizar frecuencias de perfiles a 100
        self._normalizar_frecuencias(resultado["perfiles"])

        # Corregir tendencias
        self._corregir_tendencias(resultado, tiene_escalas, tamaños_escala)

        # Normalizar frecuencias de tendencias a 100
        if resultado["tendencias_escalas"]:
            self._normalizar_frecuencias(resultado["tendencias_escalas"])

        # Enriquecer perfiles con tendencia sugerida y reglas de coherencia
        self._enriquecer_perfiles(resultado["perfiles"], ref_map, resultado["tendencias_escalas"])

        # Corregir reglas de dependencia
        resultado["reglas_dependencia"] = self._corregir_reglas(
            resultado["reglas_dependencia"], ref_map
        )

        return resultado

    def _corregir_nombres_preguntas(self, respuestas: dict, ref_map: dict) -> dict:
        """Corrige nombres de preguntas que no coinciden exactamente (fuzzy match)."""
        corregidas = {}
        ref_textos = list(ref_map.keys())

        for texto_ia, config in respuestas.items():
            if texto_ia in ref_map:
                corregidas[texto_ia] = config
                continue

            # Buscar match más cercano
            mejor_match = None
            mejor_ratio = 0
            for ref_texto in ref_textos:
                ratio = SequenceMatcher(None, texto_ia.lower(), ref_texto.lower()).ratio()
                if ratio > mejor_ratio:
                    mejor_ratio = ratio
                    mejor_match = ref_texto

            if mejor_match and mejor_ratio > 0.7:
                corregidas[mejor_match] = config
                if mejor_ratio < 1.0:
                    print(f"    [~] Corregido: '{texto_ia[:30]}...' → '{mejor_match[:30]}...' ({mejor_ratio:.0%})")
            else:
                # No hay match, mantener por si es válido
                corregidas[texto_ia] = config

        return corregidas

    def _corregir_respuesta(self, config: dict, ref: dict = None) -> dict:
        """Corrige una respuesta individual usando la referencia del formulario."""
        if not isinstance(config, dict):
            return {"tipo": "fijo", "valor": str(config)}

        tipo = config.get("tipo", "")

        # Corregir tipos inválidos
        tipo_map = {
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
        if tipo in tipo_map:
            config["tipo"] = tipo_map[tipo]
            tipo = config["tipo"]

        # Si tenemos referencia, forzar el tipo correcto
        if ref:
            tipo_ref = ref["tipo"]
            opciones_ref = ref.get("opciones", [])

            if tipo_ref in ("opcion_multiple", "seleccion_multiple", "desplegable"):
                config["tipo"] = "aleatorio"
                tipo = "aleatorio"
                # Corregir opciones para que coincidan con el formulario
                if opciones_ref:
                    config["opciones"] = self._corregir_opciones(
                        config.get("opciones", {}), opciones_ref
                    )
            elif tipo_ref == "numero":
                config["tipo"] = "rango"
                tipo = "rango"
                if "min" not in config:
                    config["min"] = 1
                if "max" not in config:
                    config["max"] = 50
                config.pop("opciones", None)
                config.pop("valor", None)
            elif tipo_ref in ("texto", "parrafo"):
                # Texto libre debe ser aleatorio con variantes
                if tipo != "aleatorio" or not config.get("opciones"):
                    valor = config.get("valor", "")
                    if valor and isinstance(valor, str):
                        config["tipo"] = "aleatorio"
                        config["opciones"] = {valor: 100}
                        config.pop("valor", None)
                    elif not config.get("opciones") or isinstance(config.get("opciones"), list):
                        config["tipo"] = "aleatorio"
                        config["opciones"] = {"Respuesta ejemplo": 100}
                tipo = config["tipo"]

        # Validar formato según tipo final
        if tipo == "aleatorio":
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
                        config["tipo"] = "fijo"
                        config["valor"] = ""
                        config.pop("opciones", None)
                        return config

            if not isinstance(config.get("opciones"), dict) or not config["opciones"]:
                valor = config.get("valor")
                if valor and isinstance(valor, str):
                    config["opciones"] = {valor: 100}
                else:
                    config["tipo"] = "fijo"
                    config["valor"] = ""
                    config.pop("opciones", None)
                    return config

            # Normalizar probabilidades a 100
            self._normalizar_opciones(config)
            config.pop("valor", None)

        elif tipo == "fijo":
            if "valor" not in config or config["valor"] is None:
                config["valor"] = ""
            config.pop("opciones", None)

        elif tipo == "rango":
            if "min" not in config:
                config["min"] = 0
            if "max" not in config:
                config["max"] = 100
            config.pop("opciones", None)
            config.pop("valor", None)

        else:
            # Tipo desconocido: inferir
            if "opciones" in config and isinstance(config["opciones"], dict) and config["opciones"]:
                config["tipo"] = "aleatorio"
                self._normalizar_opciones(config)
            elif "valor" in config and config["valor"] is not None:
                config["tipo"] = "fijo"
            elif "min" in config and "max" in config:
                config["tipo"] = "rango"
            else:
                config["tipo"] = "fijo"
                config["valor"] = ""

        return config

    def _corregir_opciones(self, opciones_ia: dict, opciones_form: list) -> dict:
        """Corrige opciones de la IA para que coincidan con las del formulario."""
        if not isinstance(opciones_ia, dict):
            # Distribución uniforme
            peso = round(100 / max(len(opciones_form), 1))
            return {op: peso for op in opciones_form}

        # Mapear opciones de la IA a las opciones reales del formulario
        resultado = {}
        opciones_form_lower = {op.lower().strip(): op for op in opciones_form}
        usadas = set()

        for key_ia, prob in opciones_ia.items():
            key_lower = key_ia.lower().strip()

            # Match exacto
            if key_lower in opciones_form_lower:
                real_key = opciones_form_lower[key_lower]
                resultado[real_key] = prob
                usadas.add(real_key)
                continue

            # Fuzzy match
            mejor_match = None
            mejor_ratio = 0
            for form_lower, form_real in opciones_form_lower.items():
                if form_real in usadas:
                    continue
                ratio = SequenceMatcher(None, key_lower, form_lower).ratio()
                if ratio > mejor_ratio:
                    mejor_ratio = ratio
                    mejor_match = form_real

            if mejor_match and mejor_ratio > 0.6:
                resultado[mejor_match] = prob
                usadas.add(mejor_match)
            # Si no hay match, descartar la opción inventada

        # Si no quedó nada, distribuir uniformemente
        if not resultado:
            peso = round(100 / max(len(opciones_form), 1))
            return {op: peso for op in opciones_form}

        return resultado

    def _normalizar_opciones(self, config: dict):
        """Normaliza las probabilidades de opciones para que sumen 100."""
        opciones = config.get("opciones", {})
        if not isinstance(opciones, dict) or not opciones:
            return
        total = sum(opciones.values())
        if total > 0 and total != 100:
            factor = 100 / total
            config["opciones"] = {k: max(1, round(v * factor)) for k, v in opciones.items()}

    def _normalizar_frecuencias(self, items: list):
        """Normaliza frecuencias de una lista de items a 100."""
        total = sum(item.get("frecuencia", 0) for item in items)
        if total > 0 and total != 100:
            factor = 100 / total
            for item in items:
                item["frecuencia"] = max(1, round(item.get("frecuencia", 0) * factor))

    def _generar_respuesta_default(self, ref_preg: dict) -> dict:
        """Genera una respuesta default para preguntas que la IA no incluyó."""
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

    def _es_escala(self, tipo: str, opciones: list = None) -> bool:
        """Determina si un tipo de pregunta es escala (incluye Likert disfrazado de opcion_multiple)."""
        if any(t in tipo.lower() for t in ("escala", "likert", "rating", "nps")):
            return True
        # Detectar Likert disfrazado: opcion_multiple con opciones tipo frecuencia/acuerdo
        if tipo == "opcion_multiple" and opciones and len(opciones) >= 3:
            opciones_lower = {o.lower().strip() for o in opciones}
            patrones_likert = [
                {"nunca", "casi nunca", "a veces", "muchas veces", "siempre"},
                {"nunca", "raramente", "a veces", "frecuentemente", "siempre"},
                {"muy en desacuerdo", "en desacuerdo", "neutral", "de acuerdo", "muy de acuerdo"},
                {"totalmente en desacuerdo", "en desacuerdo", "ni de acuerdo ni en desacuerdo", "de acuerdo", "totalmente de acuerdo"},
                {"nada", "poco", "algo", "bastante", "mucho"},
                {"never", "rarely", "sometimes", "often", "always"},
            ]
            for patron in patrones_likert:
                if len(opciones_lower & patron) >= 3:
                    return True
        return False

    def _enriquecer_perfiles(self, perfiles: list, ref_map: dict, tendencias: list):
        """Completa metadatos de coherencia por perfil para usarlos al generar respuestas."""
        nombres_tendencia = [t.get("nombre", "") for t in tendencias if t.get("nombre")]

        for perfil in perfiles:
            preferidas = self._normalizar_tendencias_preferidas(
                perfil.get("tendencias_preferidas"), nombres_tendencia
            )
            if preferidas:
                perfil["tendencias_preferidas"] = preferidas
            elif "tendencias_preferidas" in perfil:
                perfil.pop("tendencias_preferidas", None)

            perfil["tendencia_sugerida"] = self._resolver_tendencia_sugerida(
                perfil, nombres_tendencia, preferidas
            )
            perfil["reglas_coherencia"] = self._generar_reglas_coherencia(
                perfil, perfil.get("reglas_coherencia"), perfil["tendencia_sugerida"]
            )

    def _resolver_tendencia_sugerida(
        self, perfil: dict, nombres_tendencia: list[str], preferidas: dict | None = None
    ) -> str | None:
        """Normaliza o infiere la tendencia sugerida mas coherente para un perfil."""
        if not nombres_tendencia:
            return None

        sugerida = self._match_nombre(perfil.get("tendencia_sugerida"), nombres_tendencia)
        if sugerida:
            return sugerida

        if preferidas:
            ordenadas = sorted(preferidas.items(), key=lambda item: item[1], reverse=True)
            if ordenadas:
                return ordenadas[0][0]

        texto = f"{perfil.get('nombre', '')} {perfil.get('descripcion', '')}".lower()
        patrones = [
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

        for claves_perfil, claves_tendencia in patrones:
            if any(token in texto for token in claves_perfil):
                for nombre in nombres_tendencia:
                    nombre_lower = nombre.lower()
                    if any(token in nombre_lower for token in claves_tendencia):
                        return nombre

        for nombre in nombres_tendencia:
            if any(token in nombre.lower() for token in ("medio", "centro", "neutro", "moderado")):
                return nombre

        return nombres_tendencia[0]

    def _normalizar_tendencias_preferidas(self, valor, nombres_tendencia: list[str]) -> dict:
        """Convierte preferencias de tendencia a un dict limpio y compatible."""
        if not valor or not nombres_tendencia:
            return {}

        normalizado = {}
        if isinstance(valor, dict):
            for nombre, peso in valor.items():
                match = self._match_nombre(nombre, nombres_tendencia)
                if not match:
                    continue
                try:
                    normalizado[match] = normalizado.get(match, 0) + max(1, int(peso))
                except Exception:
                    normalizado[match] = normalizado.get(match, 0) + 1
        elif isinstance(valor, list):
            peso = round(100 / max(len(valor), 1))
            for nombre in valor:
                match = self._match_nombre(nombre, nombres_tendencia)
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
        """Genera reglas cortas para que el perfil mantenga coherencia interna."""
        reglas = []
        if isinstance(reglas_existentes, list):
            for regla in reglas_existentes:
                texto = str(regla).strip()
                if texto and texto not in reglas:
                    reglas.append(texto)

        respuestas = perfil.get("respuestas", {})
        edad = self._buscar_respuesta_por_keywords(respuestas, ("edad", "age"))
        sexo = self._buscar_respuesta_por_keywords(respuestas, ("sexo", "género", "genero", "gender"))
        estado_civil = self._buscar_respuesta_por_keywords(respuestas, ("estado civil", "civil"))
        instruccion = self._buscar_respuesta_por_keywords(
            respuestas, ("grado de instrucción", "grado de instruccion", "instrucción", "instruccion", "educación", "educacion")
        )
        ocupacion = self._buscar_respuesta_por_keywords(respuestas, ("ocupación", "ocupacion", "trabaja", "estudia"))
        convivencia = self._buscar_respuesta_por_keywords(respuestas, ("vive", "convive", "con quien vive"))
        hijos = self._buscar_respuesta_por_keywords(respuestas, ("hijos", "hijo", "hija"))

        if edad:
            reglas.append(f"Edad base del perfil: {edad}. Mantener respuestas compatibles con ese rango etario.")
        if sexo:
            reglas.append(f"Sexo o género dominante del perfil: {sexo}. Evitar contradicciones con preguntas derivadas.")
        if estado_civil and convivencia:
            reglas.append(f"Estado civil y convivencia deben ser consistentes entre sí: {estado_civil} / {convivencia}.")
        elif estado_civil:
            reglas.append(f"El estado civil dominante es {estado_civil}; evitar combinaciones improbables con el resto del perfil.")
        if instruccion and ocupacion:
            reglas.append(f"Ocupación e instrucción deben ir juntas: {ocupacion} con {instruccion}.")
        elif ocupacion:
            reglas.append(f"La ocupación principal del perfil es {ocupacion}; mantener consistencia con edad y contexto.")
        if hijos:
            hijos_lower = hijos.lower()
            if any(token in hijos_lower for token in ("no", "ninguno", "0")):
                reglas.append("Si el perfil no tiene hijos, usar 0 o no aplica en preguntas derivadas sobre hijos.")
            else:
                reglas.append("Si el perfil tiene hijos, mantener consistencia en cantidad, convivencia y responsabilidades familiares.")
        if tendencia_sugerida:
            reglas.append(f"Para preguntas de escala, este perfil debe inclinarse hacia la tendencia '{tendencia_sugerida}'.")

        reglas.append("Las respuestas sensibles deben seguir la misma narrativa general del perfil y no cambiar de dirección sin motivo.")

        unicas = []
        for regla in reglas:
            texto = str(regla).strip()
            if texto and texto not in unicas:
                unicas.append(texto)

        return unicas[:5]

    def _buscar_respuesta_por_keywords(self, respuestas: dict, keywords: tuple[str, ...]) -> str | None:
        """Busca la respuesta dominante de una pregunta usando palabras clave."""
        for pregunta, config in respuestas.items():
            texto = pregunta.lower()
            if any(keyword in texto for keyword in keywords):
                return self._resumen_respuesta(config)
        return None

    def _resumen_respuesta(self, config: dict) -> str:
        """Resume una configuración de respuesta para usarla en reglas de coherencia."""
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
                mejor = max(opciones.items(), key=lambda item: item[1])[0]
                return str(mejor)
        return ""

    def _match_nombre(self, valor: str | None, candidatos: list[str]) -> str | None:
        """Hace match exacto o difuso contra nombres cortos como tendencias."""
        if not valor or not candidatos:
            return None
        if valor in candidatos:
            return valor

        valor_lower = str(valor).lower().strip()
        mejor = None
        mejor_ratio = 0
        for candidato in candidatos:
            ratio = SequenceMatcher(None, valor_lower, candidato.lower().strip()).ratio()
            if ratio > mejor_ratio:
                mejor_ratio = ratio
                mejor = candidato
        return mejor if mejor_ratio >= 0.7 else None

    # ========== TENDENCIAS ==========

    def _corregir_tendencias(self, resultado: dict, tiene_escalas: bool, tamaños: set):
        """Corrige o genera tendencias de escala."""
        tendencias = resultado.get("tendencias_escalas", [])

        # Si no hay escalas, limpiar tendencias
        if not tiene_escalas:
            resultado["tendencias_escalas"] = []
            return

        # Corregir "distribucion" → "distribuciones" y asegurar tamaños correctos
        for t in tendencias:
            if "distribucion" in t and "distribuciones" not in t:
                dist = t.pop("distribucion")
                if isinstance(dist, list):
                    t["distribuciones"] = {str(len(dist)): dist}

            if "distribuciones" not in t:
                t["distribuciones"] = {}

            # Asegurar que hay distribución para cada tamaño de escala
            for tam in tamaños:
                tam_str = str(tam)
                if tam_str not in t["distribuciones"]:
                    # Generar distribución centrada
                    t["distribuciones"][tam_str] = self._dist_centrada(tam)

            # Normalizar cada distribución a 100
            for tam_str, dist in t["distribuciones"].items():
                total = sum(dist)
                if total > 0 and total != 100:
                    t["distribuciones"][tam_str] = [
                        max(1, round(v * 100 / total)) for v in dist
                    ]

        # Si hay escalas pero no hay tendencias, generar defaults
        if not tendencias and tiene_escalas:
            distribuciones_medio = {}
            distribuciones_alto = {}
            distribuciones_bajo = {}
            for tam in tamaños:
                distribuciones_medio[str(tam)] = self._dist_centrada(tam)
                distribuciones_alto[str(tam)] = self._dist_sesgada_alta(tam)
                distribuciones_bajo[str(tam)] = self._dist_sesgada_baja(tam)

            resultado["tendencias_escalas"] = [
                {
                    "nombre": "Término Medio",
                    "descripcion": "Responde en valores centrales",
                    "frecuencia": 50,
                    "distribuciones": distribuciones_medio,
                },
                {
                    "nombre": "Centro-Alto",
                    "descripcion": "Responde ligeramente por encima del centro",
                    "frecuencia": 25,
                    "distribuciones": distribuciones_alto,
                },
                {
                    "nombre": "Centro-Bajo",
                    "descripcion": "Responde ligeramente por debajo del centro",
                    "frecuencia": 25,
                    "distribuciones": distribuciones_bajo,
                },
            ]

    def _dist_centrada(self, tam: int) -> list:
        """Genera distribución centrada (campana) para escala de tamaño tam."""
        centro = (tam - 1) / 2
        dist = []
        for i in range(tam):
            peso = max(1, round(40 * (1 / (1 + abs(i - centro)))))
            dist.append(peso)
        total = sum(dist)
        return [round(v * 100 / total) for v in dist]

    def _dist_sesgada_alta(self, tam: int) -> list:
        """Genera distribución sesgada hacia arriba."""
        centro = (tam - 1) * 0.6  # Ligeramente arriba del centro
        dist = []
        for i in range(tam):
            peso = max(1, round(40 * (1 / (1 + abs(i - centro)))))
            dist.append(peso)
        total = sum(dist)
        return [round(v * 100 / total) for v in dist]

    def _dist_sesgada_baja(self, tam: int) -> list:
        """Genera distribución sesgada hacia abajo."""
        centro = (tam - 1) * 0.4  # Ligeramente debajo del centro
        dist = []
        for i in range(tam):
            peso = max(1, round(40 * (1 / (1 + abs(i - centro)))))
            dist.append(peso)
        total = sum(dist)
        return [round(v * 100 / total) for v in dist]

    # ========== REGLAS ==========

    def _corregir_reglas(self, reglas: list, ref_map: dict) -> list:
        """Corrige nombres de preguntas en las reglas de dependencia."""
        ref_textos = list(ref_map.keys())
        reglas_corregidas = []

        for regla in reglas:
            si_preg = regla.get("si_pregunta", "")
            entonces_preg = regla.get("entonces_pregunta", "")

            # Corregir nombres de preguntas
            regla["si_pregunta"] = self._match_pregunta(si_preg, ref_textos) or si_preg
            regla["entonces_pregunta"] = self._match_pregunta(entonces_preg, ref_textos) or entonces_preg

            # Asegurar campos requeridos
            if "operador" not in regla:
                regla["operador"] = "igual"
            if "entonces_excluir" not in regla:
                regla["entonces_excluir"] = []
            if "entonces_forzar" not in regla:
                regla["entonces_forzar"] = None

            reglas_corregidas.append(regla)

        return reglas_corregidas

    def _match_pregunta(self, texto: str, ref_textos: list) -> str | None:
        """Busca la pregunta más similar en la referencia."""
        if texto in ref_textos:
            return texto

        mejor = None
        mejor_ratio = 0
        for ref in ref_textos:
            ratio = SequenceMatcher(None, texto.lower(), ref.lower()).ratio()
            if ratio > mejor_ratio:
                mejor_ratio = ratio
                mejor = ref

        return mejor if mejor_ratio > 0.7 else None

    # ========== FALLBACK ==========

    def _generar_fallback(self, estructura: dict) -> dict:
        """Genera configuración básica si la IA falla."""
        print("  Usando configuración fallback (sin IA)")

        preguntas = []
        tiene_escalas = False
        tamaños_escala = set()

        for pagina in estructura.get("paginas", []):
            for pregunta in pagina.get("preguntas", []):
                tipo = pregunta.get("tipo", "")
                if tipo in ("informativo", "desconocido", ""):
                    continue
                preguntas.append(pregunta)
                opts = pregunta.get("opciones", [])
                if self._es_escala(tipo, opts):
                    tiene_escalas = True
                    n_opts = len(opts)
                    if n_opts > 0:
                        tamaños_escala.add(n_opts)

        perfil_base = {
            "nombre": "General",
            "descripcion": "Perfil genérico con respuestas aleatorias",
            "frecuencia": 100,
            "tendencia_sugerida": None,
            "reglas_coherencia": [
                "Mantener consistencia básica entre edad, ocupación y estudios.",
                "Responder las escalas con una tendencia estable y no contradictoria.",
            ],
            "respuestas": {},
        }

        for pregunta in preguntas:
            ref = {
                "texto": pregunta["texto"],
                "tipo": pregunta.get("tipo", ""),
                "opciones": pregunta.get("opciones", []),
            }
            if not self._es_escala(ref["tipo"], ref.get("opciones", [])):
                perfil_base["respuestas"][ref["texto"]] = self._generar_respuesta_default(ref)

        # Tendencias solo si hay escalas
        tendencias = []
        if tiene_escalas:
            distribuciones_medio = {}
            distribuciones_alto = {}
            distribuciones_bajo = {}
            for tam in tamaños_escala:
                distribuciones_medio[str(tam)] = self._dist_centrada(tam)
                distribuciones_alto[str(tam)] = self._dist_sesgada_alta(tam)
                distribuciones_bajo[str(tam)] = self._dist_sesgada_baja(tam)

            tendencias = [
                {
                    "nombre": "Término Medio",
                    "descripcion": "Responde en valores centrales",
                    "frecuencia": 50,
                    "distribuciones": distribuciones_medio,
                },
                {
                    "nombre": "Centro-Alto",
                    "descripcion": "Responde ligeramente por encima del centro",
                    "frecuencia": 25,
                    "distribuciones": distribuciones_alto,
                },
                {
                    "nombre": "Centro-Bajo",
                    "descripcion": "Responde ligeramente por debajo del centro",
                    "frecuencia": 25,
                    "distribuciones": distribuciones_bajo,
                },
            ]
            perfil_base["tendencia_sugerida"] = "Término Medio"

        # Generar reglas básicas automáticas
        reglas = self._generar_reglas_fallback(preguntas)

        return {
            "perfiles": [perfil_base],
            "reglas_dependencia": reglas,
            "tendencias_escalas": tendencias,
        }

    def _generar_reglas_fallback(self, preguntas: list) -> list:
        """Genera reglas de dependencia básicas detectando patrones comunes."""
        import re
        reglas = []

        for preg in preguntas:
            texto_lower = preg["texto"].lower()
            opciones = preg.get("opciones", [])
            opciones_lower = [o.lower() for o in opciones]

            # Patrón: ¿Tiene hijos? → preguntas sobre hijos
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

            # Patrón: ¿Trabaja? / ¿Estudia? → preguntas sobre ocupación
            if re.search(r'\btrabaja\b|\bempleo\b|\bsituaci[oó]n laboral\b', texto_lower):
                for otra in preguntas:
                    otra_lower = otra["texto"].lower()
                    if otra["texto"] != preg["texto"] and re.search(r'\bocupaci[oó]n\b|\bcargo\b|\bempresa\b|\bdonde trabaja\b', otra_lower):
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
