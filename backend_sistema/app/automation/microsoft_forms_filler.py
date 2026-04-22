"""
Llenador de formularios Microsoft Forms.
Para agregar soporte a un nuevo tipo de campo: implementar en ms_forms_filler.py.
"""
import logging
import time

from app.automation.base_filler import BaseFiller

logger = logging.getLogger(__name__)
from app.automation.ms_forms_filler import MSFormsFiller
from app.automation.navigation.button_detector import verificar_envio
from app.automation.navigation.selectors import detectar_plataforma
from app.automation.navigation.waits import wait_for_form_ready


class MicrosoftFormsFiller(BaseFiller):
    """Llena Microsoft Forms delegando el llenado por página a MSFormsFiller."""

    def __init__(self):
        self.ms_filler = MSFormsFiller()

    def fill_form(
        self,
        page,
        respuesta_generada: dict,
        url: str,
        numero: int,
        runtime_config: dict | None = None,
    ) -> tuple[bool, float]:
        inicio = time.time()
        perfil = respuesta_generada.get("_perfil", "?")
        platform = detectar_plataforma(url)
        if platform["name"] != "microsoft_forms":
            raise ValueError("MicrosoftFormsFiller solo soporta Microsoft Forms.")

        logger.info("ENCUESTA #%s | %s | Perfil: %s", numero, platform["name"], perfil)

        page.goto(url, wait_until="domcontentloaded")
        wait_for_form_ready(page, url, runtime_config)

        paginas = respuesta_generada.get("paginas", [])
        ms_submit_result = None
        ms_page_failed = False

        for pag_idx, pagina in enumerate(paginas):
            logger.debug("Pág %s/%s", pag_idx + 1, len(paginas))
            wait_for_form_ready(page, url, runtime_config)
            respuestas = pagina.get("respuestas", [])
            botones = pagina.get("botones", [])

            ms_result = self.ms_filler.fill_page(page, respuestas, runtime_config=runtime_config)
            if not ms_result.get("ok", False):
                ms_page_failed = True
                failed = ms_result.get("failed_questions", [])
                preview = "; ".join(q[:50] for q in failed[:3])
                logger.warning("[MS] Abortando pagina: %s pregunta(s) no llenadas. Fallidas: %s", ms_result.get("failed", 0), preview or "—")
                break

            if "Siguiente" in botones:
                self.ms_filler.click_next(page, url=url, runtime_config=runtime_config)
            elif "Enviar" in botones:
                ms_submit_result = self.ms_filler.click_submit(page, url=url, runtime_config=runtime_config)

        if ms_page_failed:
            exito = False
        elif ms_submit_result is not None:
            exito = ms_submit_result
        else:
            exito = verificar_envio(page, url, submit_clicked=False, runtime_config=runtime_config)
        tiempo = time.time() - inicio

        status = "Enviada" if exito else "No confirmada"
        logger.info("Encuesta #%s %s en %.1fs", numero, status, tiempo)

        return exito, tiempo
