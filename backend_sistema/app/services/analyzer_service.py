"""
Orquestador de análisis de encuestas con IA.

Este archivo solo coordina el flujo: preparar → llamar IA → validar → enriquecer.
Para cambiar el comportamiento de cualquier paso, editar el submódulo correspondiente
en app/services/analysis/ sin tocar este archivo.
"""
import json
import logging
from app.ai.prompts import PROMPT_SISTEMA_ANALISIS, PROMPT_ANALISIS_ENCUESTA
from app.services.ai_service import AIService

logger = logging.getLogger(__name__)
from app.database.models import PromptTemplate
from app.services.analysis import (
    SurveyPreparator,
    ResponseNormalizer,
    ProfileManager,
    ProfileEnricher,
    TendencyManager,
    RulesManager,
)
from app.services.analysis.survey_preparator import es_escala


class AnalyzerService:
    """Orquesta el análisis de encuestas delegando cada responsabilidad a su clase."""

    def __init__(self, ai_service: AIService):
        self.ai = ai_service
        self._preparator = SurveyPreparator()
        self._normalizer = ResponseNormalizer()
        self._profile_manager = ProfileManager(self._normalizer)
        self._enricher = ProfileEnricher()
        self._tendency_manager = TendencyManager()
        self._rules_manager = RulesManager()

    def analyze(self, estructura_scrapeada: dict, instrucciones_extra: str = "") -> dict:
        """Analiza la estructura scrapeada y retorna configuración de perfiles lista para usar."""
        resumen = self._preparator.preparar_resumen(estructura_scrapeada)
        preguntas_ref = self._preparator.extraer_preguntas_referencia(estructura_scrapeada)

        logger.info("Enviando estructura a IA para análisis...")
        try:
            resultado = self._llamar_ia(resumen, instrucciones_extra)
            resultado = self._validar_y_corregir(resultado, preguntas_ref)
            logger.info(
                "IA generó: %d perfiles, %d reglas, %d tendencias",
                len(resultado.get("perfiles", [])),
                len(resultado.get("reglas_dependencia", [])),
                len(resultado.get("tendencias_escalas", [])),
            )
            return resultado
        except Exception as e:
            logger.error("Error llamando a IA, usando fallback: %s", e, exc_info=True)
            return self._generar_fallback(estructura_scrapeada, preguntas_ref)

    # ── flujo interno ──────────────────────────────────────────────────────────

    def _llamar_ia(self, resumen: dict, instrucciones_extra: str) -> dict:
        system_prompt = PROMPT_SISTEMA_ANALISIS
        user_prompt_tpl = PROMPT_ANALISIS_ENCUESTA
        try:
            p_sys = PromptTemplate.query.filter_by(slug="system_analysis").first()
            if p_sys and not p_sys.is_default:
                system_prompt = p_sys.contenido
            p_usr = PromptTemplate.query.filter_by(slug="user_analysis").first()
            if p_usr and not p_usr.is_default:
                user_prompt_tpl = p_usr.contenido
        except Exception as e:
            logger.warning("No se pudieron cargar prompts personalizados de BD, usando defaults: %s", e)

        provider = self.ai.get_provider()
        num_preguntas = len(resumen.get("preguntas", []))
        max_tokens = max(6000, min(16000, num_preguntas * 300))
        logger.debug("Preguntas para perfiles: %s, max_tokens: %s", num_preguntas, max_tokens)

        user_prompt = user_prompt_tpl.format(
            encuesta_json=json.dumps(resumen, ensure_ascii=False, indent=2)
        )
        if instrucciones_extra:
            user_prompt += (
                f"\n\n═══════════════════════════════════════\n"
                f"INSTRUCCIONES ADICIONALES DEL USUARIO:\n"
                f"═══════════════════════════════════════\n{instrucciones_extra}\n"
            )

        contenido = provider.chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7,
            max_tokens=max_tokens,
            json_mode=True,
        )
        return json.loads(contenido)

    def _validar_y_corregir(self, resultado: dict, preguntas_ref: list) -> dict:
        resultado.setdefault("perfiles", [])
        resultado.setdefault("reglas_dependencia", [])
        resultado.setdefault("tendencias_escalas", [])

        ref_map = {p["texto"]: p for p in preguntas_ref}
        tiene_escalas, tamaños_escala = self._detectar_escalas(preguntas_ref)

        # Corregir cada perfil
        for perfil in resultado["perfiles"]:
            perfil.setdefault("respuestas", {})
            perfil["respuestas"] = self._normalizer.corregir_nombres_preguntas(perfil["respuestas"], ref_map)

            for texto, config in list(perfil["respuestas"].items()):
                perfil["respuestas"][texto] = self._normalizer.corregir_respuesta(config, ref_map.get(texto))

            for ref in preguntas_ref:
                texto = ref["texto"]
                if texto not in perfil["respuestas"] and not es_escala(ref["tipo"], ref.get("opciones", [])):
                    perfil["respuestas"][texto] = self._normalizer.generar_respuesta_default(ref)
                    logger.debug("[+] Agregada pregunta faltante: %s...", texto[:40])

            for texto in list(perfil["respuestas"].keys()):
                ref = ref_map.get(texto)
                if ref and es_escala(ref["tipo"], ref.get("opciones", [])):
                    del perfil["respuestas"][texto]

        # Perfiles: cantidad, sanitización y frecuencias
        resultado["perfiles"] = self._profile_manager.asegurar_cantidad(resultado["perfiles"], preguntas_ref)
        self._profile_manager.sanitizar_no_soportados(resultado["perfiles"], preguntas_ref)
        self._normalizer.normalizar_frecuencias(resultado["perfiles"])

        # Tendencias
        self._tendency_manager.corregir(resultado, tiene_escalas, tamaños_escala)
        resultado["tendencias_escalas"] = self._tendency_manager.asegurar_cantidad(
            resultado["tendencias_escalas"], tamaños_escala
        )
        if resultado["tendencias_escalas"]:
            self._normalizer.normalizar_frecuencias(resultado["tendencias_escalas"])

        # Enriquecer perfiles con tendencia sugerida y reglas de coherencia
        self._enricher.enriquecer(resultado["perfiles"], ref_map, resultado["tendencias_escalas"])

        # Reglas de dependencia
        resultado["reglas_dependencia"] = self._rules_manager.corregir_reglas(
            resultado["reglas_dependencia"], ref_map
        )

        return resultado

    def _generar_fallback(self, estructura: dict, preguntas_ref: list) -> dict:
        logger.info("Usando configuración fallback (sin IA)")
        _, tamaños_escala = self._detectar_escalas(preguntas_ref)

        perfiles = self._profile_manager.crear_defaults(preguntas_ref, 3)
        for perfil in perfiles:
            perfil["tendencia_sugerida"] = "Término Medio"
            perfil["reglas_coherencia"] = [
                "Mantener coherencia entre las respuestas del mismo perfil.",
                "Evitar suposiciones demográficas no preguntadas en el formulario.",
            ]

        preguntas_raw = [
            p
            for pagina in estructura.get("paginas", [])
            for p in pagina.get("preguntas", [])
            if p.get("tipo") not in ("informativo", "desconocido", "")
        ]

        return {
            "perfiles": perfiles,
            "reglas_dependencia": self._rules_manager.generar_reglas_fallback(preguntas_raw),
            "tendencias_escalas": self._tendency_manager.crear_defaults(tamaños_escala or {5, 7, 11}),
        }

    def _detectar_escalas(self, preguntas_ref: list) -> tuple[bool, set]:
        tiene_escalas = False
        tamaños: set = set()
        for p in preguntas_ref:
            if es_escala(p["tipo"], p.get("opciones", [])):
                tiene_escalas = True
                n = len(p.get("opciones", []))
                if n > 0:
                    tamaños.add(n)
        return tiene_escalas, tamaños
