"""
Llenador genérico para formularios de cualquier plataforma.
Detecta la plataforma y delega al filler especializado.
Usa FillingStrategies compartidas para plataformas genéricas.
"""
import time

from app.automation.base_filler import BaseFiller
from app.automation.filling_strategies import FillingStrategies
from app.automation.ms_forms_filler import MSFormsFiller
from app.automation.navigation.button_detector import click_boton, verificar_envio
from app.automation.navigation.selectors import detectar_plataforma
from app.automation.navigation.waits import wait_for_form_ready
from app.automation.timing import pause_action
from app.constants.question_types import TIPOS_NO_LLENABLES

fs = FillingStrategies()

# Selectores genéricos para plataformas no-Google, no-MS
GENERIC_TEXT_SELECTORS = [
    'input[type="text"]',
    'input:not([type])',
    'input[type="number"]',
    'input:not([type="radio"]):not([type="checkbox"]):not([type="hidden"])',
]
GENERIC_TEXTAREA_SELECTORS = [
    'textarea',
    '[contenteditable="true"]',
]
GENERIC_CONTAINER_SELECTORS = [
    '[class*="question"]',
    '.form-group',
    'fieldset',
    '[role="group"]',
    '[class*="field"]',
    '[class*="item"]',
]


class GenericFiller(BaseFiller):
    """Llena formularios detectando la plataforma automáticamente."""

    def __init__(self, ai_service=None):
        self.ms_filler = MSFormsFiller()

    def fill_form(
        self,
        page,
        respuesta_generada: dict,
        url: str,
        numero: int,
        runtime_config: dict | None = None,
    ) -> tuple[bool, float]:
        """Llena un formulario detectando la plataforma."""
        inicio = time.time()
        perfil = respuesta_generada.get("_perfil", "?")
        platform = detectar_plataforma(url)

        print(f"\n{'='*55}")
        print(f"  ENCUESTA #{numero} | {platform['name']} | Perfil: {perfil}")
        print(f"{'='*55}")

        page.goto(url, wait_until="domcontentloaded")
        wait_for_form_ready(page, url, runtime_config)

        paginas = respuesta_generada.get("paginas", [])
        is_ms = platform["name"] == "microsoft_forms"
        ms_submit_result = None
        submit_clicked = False

        for pag_idx, pagina in enumerate(paginas):
            print(f"  [Pág {pag_idx + 1}/{len(paginas)}]")
            wait_for_form_ready(page, url, runtime_config)
            respuestas = pagina.get("respuestas", [])
            botones = pagina.get("botones", [])

            if is_ms:
                self.ms_filler.fill_page(page, respuestas, runtime_config=runtime_config)
            else:
                self._fill_generic_page(page, respuestas, runtime_config=runtime_config)

            if "Siguiente" in botones:
                if is_ms:
                    self.ms_filler.click_next(page, url=url, runtime_config=runtime_config)
                else:
                    click_boton(page, "Siguiente", url, runtime_config=runtime_config)
            elif "Enviar" in botones:
                if is_ms:
                    ms_submit_result = self.ms_filler.click_submit(page, url=url, runtime_config=runtime_config)
                else:
                    submit_clicked = click_boton(page, "Enviar", url, runtime_config=runtime_config)

        # Para MS Forms, click_submit ya verificó el envío internamente
        if is_ms and ms_submit_result is not None:
            exito = ms_submit_result
        else:
            exito = verificar_envio(page, url, submit_clicked=submit_clicked, runtime_config=runtime_config)
        tiempo = time.time() - inicio

        status = "Enviada" if exito else "No confirmada"
        print(f"  {status}! {tiempo:.1f}s")

        return exito, tiempo

    # ========== GENÉRICO (Typeform, SurveyMonkey, etc) ==========

    def _fill_generic_page(self, page, respuestas: list, runtime_config: dict | None = None):
        """Llena una página de formulario genérico usando FillingStrategies."""
        for resp in respuestas:
            tipo = resp["tipo"]
            valor = resp["valor"]
            pregunta = resp["pregunta"]

            if tipo in TIPOS_NO_LLENABLES:
                print(f"    SKIP ({tipo}): {pregunta[:50]}")
                continue

            container = fs.find_question_container(page, pregunta, GENERIC_CONTAINER_SELECTORS)
            filled = False

            if container:
                filled = self._fill_in_container(container, page, tipo, valor, runtime_config=runtime_config)
            else:
                # Sin contenedor: intentar llenado secuencial
                if tipo in ("texto", "numero", "fecha", "hora"):
                    filled = fs.fill_text(page, str(valor), GENERIC_TEXT_SELECTORS, runtime_config=runtime_config)
                elif tipo == "parrafo":
                    filled = fs.fill_textarea(page, str(valor), GENERIC_TEXTAREA_SELECTORS, runtime_config=runtime_config)
                elif tipo in ("opcion_multiple", "escala_lineal", "nps"):
                    filled = fs.click_option_by_text(page, page, str(valor), "radio", runtime_config=runtime_config)

            if filled:
                print(f"    OK: {pregunta[:50]}")
            else:
                print(f"    FALLÓ: {pregunta[:50]}")

            pause_action(runtime_config)

    def _fill_in_container(self, container, page, tipo: str, valor, runtime_config: dict | None = None) -> bool:
        """Llena un campo dentro de su contenedor usando FillingStrategies."""
        try:
            if tipo in ("texto", "numero"):
                return fs.fill_text(container, str(valor), GENERIC_TEXT_SELECTORS, runtime_config=runtime_config)

            elif tipo == "parrafo":
                return fs.fill_textarea(container, str(valor), GENERIC_TEXTAREA_SELECTORS, runtime_config=runtime_config)

            elif tipo in ("opcion_multiple", "escala_lineal", "nps"):
                return fs.click_option_by_text(container, page, str(valor), "radio", runtime_config=runtime_config)

            elif tipo == "seleccion_multiple":
                return fs.click_multiple_options(container, page, valor, "checkbox", runtime_config=runtime_config)

            elif tipo == "desplegable":
                return fs.fill_dropdown(container, page, str(valor), runtime_config=runtime_config)

            elif tipo == "fecha":
                return fs.fill_date(container, str(valor), runtime_config=runtime_config)

            elif tipo == "hora":
                return fs.fill_time(container, str(valor), runtime_config=runtime_config)

            elif tipo in ("likert", "matriz", "matriz_checkbox"):
                return fs.fill_matrix(container, page, valor, runtime_config=runtime_config)

            elif tipo == "ranking":
                return fs.fill_ranking(container, page, valor, runtime_config=runtime_config)

            else:
                return fs.auto_detect_and_fill(container, page, valor, runtime_config=runtime_config)

        except Exception as e:
            print(f"    [Generic] Error {tipo}: {e}")
            return False
