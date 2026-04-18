"""
Orquestador auxiliar para Microsoft Forms.
"""
import time

from app.automation.base_filler import BaseFiller
from app.automation.ms_forms_filler import MSFormsFiller
from app.automation.navigation.button_detector import verificar_envio
from app.automation.navigation.selectors import detectar_plataforma
from app.automation.navigation.waits import wait_for_form_ready


class GenericFiller(BaseFiller):
    """Llena Microsoft Forms reutilizando estrategias compartidas."""

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
        """Llena un formulario Microsoft Forms."""
        inicio = time.time()
        perfil = respuesta_generada.get("_perfil", "?")
        platform = detectar_plataforma(url)
        if platform["name"] != "microsoft_forms":
            raise ValueError("GenericFiller solo soporta Microsoft Forms en la ruta activa.")

        print(f"\n{'='*55}")
        print(f"  ENCUESTA #{numero} | {platform['name']} | Perfil: {perfil}")
        print(f"{'='*55}")

        page.goto(url, wait_until="domcontentloaded")
        wait_for_form_ready(page, url, runtime_config)

        paginas = respuesta_generada.get("paginas", [])
        ms_submit_result = None
        ms_page_failed = False

        for pag_idx, pagina in enumerate(paginas):
            print(f"  [Pág {pag_idx + 1}/{len(paginas)}]")
            wait_for_form_ready(page, url, runtime_config)
            respuestas = pagina.get("respuestas", [])
            botones = pagina.get("botones", [])

            ms_result = self.ms_filler.fill_page(page, respuestas, runtime_config=runtime_config)
            if not ms_result.get("ok", False):
                ms_page_failed = True
                failed = ms_result.get("failed_questions", [])
                preview = "; ".join(q[:50] for q in failed[:3])
                print(f"    [MS] Abortando pagina: {ms_result.get('failed', 0)} pregunta(s) no se llenaron")
                if preview:
                    print(f"    [MS] Fallidas: {preview}")
                break

            if ms_page_failed:
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
        print(f"  {status}! {tiempo:.1f}s")

        return exito, tiempo
