"""
Orquestador de llenado para Google Forms.

Solo coordina el flujo por página. La lógica de cada tipo de interacción
vive en app/automation/gforms/. Para agregar soporte a un nuevo tipo de pregunta,
editar solo el handler correspondiente sin tocar este archivo.
"""
import time

from app.automation.base_filler import BaseFiller
from app.automation.navigation.button_detector import click_boton, verificar_envio
from app.automation.navigation.waits import wait_for_form_ready
from app.automation.timing import pause_action
from app.constants.question_types import TIPOS_NO_LLENABLES
from app.automation.gforms import (
    QuestionFinder,
    OptionClicker,
    TextWriter,
    DropdownHandler,
    SpecialInputHandler,
)


class GoogleFormsFiller(BaseFiller):
    """Llena formularios de Google Forms delegando cada tipo al handler correcto."""

    def __init__(self):
        self._finder = QuestionFinder()
        self._clicker = OptionClicker()
        self._writer = TextWriter()
        self._dropdown = DropdownHandler()
        self._special = SpecialInputHandler()

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
        tendencia = respuesta_generada.get("_tendencia", "?")

        print(f"\n{'='*55}")
        print(f"  ENCUESTA #{numero} | Perfil: {perfil} | Tendencia: {tendencia}")
        print(f"{'='*55}")

        page.goto(url, wait_until="domcontentloaded")
        wait_for_form_ready(page, url, runtime_config)

        paginas = respuesta_generada.get("paginas", [])
        speed_profile = runtime_config.get("speed_profile") if runtime_config else None
        fast_mode = speed_profile in ("turbo", "turbo_plus")
        aggressive_mode = speed_profile == "turbo_plus"

        if paginas and paginas[0].get("respuestas"):
            self._skip_informational_pages(page, url, runtime_config)

        submit_clicked = False
        aborted = False
        for pag_idx, pagina in enumerate(paginas):
            print(f"  [Pag {pag_idx + 1}/{len(paginas)}]")
            wait_for_form_ready(page, url, runtime_config)
            submit_clicked, broke = self._fill_page(
                page, pagina, paginas, pag_idx, url,
                fast_mode, aggressive_mode, runtime_config
            )
            if broke:
                aborted = True
                break

        exito = False if aborted and not submit_clicked else verificar_envio(
            page, url, submit_clicked=submit_clicked, runtime_config=runtime_config
        )
        tiempo = time.time() - inicio
        print(f"  {'Enviada' if exito else 'No confirmada'}! {_format_time(tiempo)}")
        return exito, tiempo

    # ── flujo por página ───────────────────────────────────────────────────────

    def _fill_page(self, page, pagina: dict, paginas: list, pag_idx: int,
                   url: str, fast_mode: bool, aggressive_mode: bool,
                   runtime_config: dict | None) -> tuple[bool, bool]:
        """Llena una página y navega al siguiente. Retorna (submit_clicked, broke)."""
        respuestas = pagina.get("respuestas", [])
        listitems = page.locator('[role="listitem"]').all()
        answerable_items = self._get_answerable_items(page, listitems, fast_mode)
        answerable_idx = 0
        escalas_pendientes = []
        failed_questions = []

        for resp in respuestas:
            tipo, valor, pregunta = resp["tipo"], resp["valor"], resp["pregunta"]
            opciones = resp.get("opciones_disponibles", [])
            if tipo in TIPOS_NO_LLENABLES:
                print(f"    SKIP ({tipo}): {pregunta[:50]}")
                continue

            fast_container = (
                answerable_items[answerable_idx]
                if answerable_items and answerable_idx < len(answerable_items)
                else None
            )
            answerable_idx += 1
            container = fast_container or self._finder.find(page, pregunta, listitems, runtime_config)

            filled = self._fill_question(page, tipo, valor, pregunta, container, escalas_pendientes, runtime_config, opciones=opciones)
            pause_action(runtime_config)

            if not filled and fast_container and not aggressive_mode:
                fallback = self._finder.find(page, pregunta, listitems, runtime_config)
                if fallback and fallback != container:
                    filled = self._fill_question(page, tipo, valor, pregunta, fallback, escalas_pendientes, runtime_config, opciones=opciones)
                    pause_action(runtime_config)

            if not filled:
                failed_questions.append(pregunta)
                print(f"      No se pudo completar: {pregunta[:60]}")

        if escalas_pendientes:
            print(f"    Respondiendo {len(escalas_pendientes)} escalas...")
            done = self._special.fill_scales(page, escalas_pendientes, runtime_config)
            if done < len(escalas_pendientes):
                failed_questions.append(f"Escalas pendientes ({len(escalas_pendientes) - done})")

        if failed_questions:
            preview = "; ".join(q[:50] for q in failed_questions[:4])
            print(f"    [Google] {len(failed_questions)} respuesta(s) no llenadas")
            if preview:
                print(f"    [Google] Fallidas: {preview}")
            if "Enviar" not in pagina.get("botones", []):
                return False, True

        botones = pagina.get("botones", [])
        if "Siguiente" in botones:
            advanced = click_boton(page, "Siguiente", url, runtime_config=runtime_config)
            next_idx = pag_idx + 1
            if not advanced and next_idx < len(paginas):
                advanced = self._matches_expected_page(page, paginas[next_idx], runtime_config)
            if not advanced:
                print("    [Google] No se pudo avanzar de página.")
                return False, True
            if next_idx < len(paginas) and paginas[next_idx].get("respuestas"):
                self._skip_informational_pages(page, url, runtime_config)
            return False, False

        if "Enviar" in botones:
            submit_clicked = click_boton(page, "Enviar", url, runtime_config=runtime_config)
            return submit_clicked, False

        return False, False

    def _fill_question(self, page, tipo: str, valor, pregunta: str,
                       container, escalas_pendientes: list, runtime_config, opciones: list | None = None) -> bool:
        """Delega el llenado al handler correcto según el tipo de pregunta."""
        if tipo == "opcion_multiple":
            print(f"    {pregunta[:50]}: {valor}")
            fn = self._clicker.click_otro if str(valor).startswith("Otro") else self._clicker.click
            return fn(page, valor, "radio", container, pregunta=pregunta, runtime_config=runtime_config)

        if tipo == "seleccion_multiple":
            print(f"    {pregunta[:50]}: {valor}")
            valores = valor if isinstance(valor, list) else [valor]
            ok = True
            for item_val in valores:
                fn = self._clicker.click_otro if str(item_val).startswith("Otro") else self._clicker.click
                ok = fn(page, item_val, "checkbox", container, pregunta=pregunta, runtime_config=runtime_config) and ok
                pause_action(runtime_config, multiplier=0.7)
            return ok

        if tipo == "parrafo":
            print(f"    {pregunta[:50]}: {str(valor)[:50]}...")
            return self._writer.write_paragraph(page, valor, container)

        if tipo in ("texto", "numero"):
            print(f"    {pregunta[:50]}: {valor}")
            return self._writer.write(page, valor, container, pregunta=pregunta, tipo=tipo)

        if tipo == "escala_lineal":
            escalas_pendientes.append((valor, container))
            return True

        if tipo == "desplegable":
            print(f"    {pregunta[:50]}: {valor}")
            return self._dropdown.select(page, pregunta, valor, container, runtime_config=runtime_config)

        if tipo == "fecha":
            print(f"    {pregunta[:50]}: {valor}")
            return self._special.fill_date(page, valor, container, text_writer=self._writer, runtime_config=runtime_config)

        if tipo == "hora":
            print(f"    {pregunta[:50]}: {valor}")
            return self._special.fill_time(page, valor, container, runtime_config=runtime_config)

        if tipo in ("matriz", "matriz_checkbox"):
            print(f"    {pregunta[:50]}: (matriz)")
            return self._special.fill_matrix(page, valor, tipo, container, runtime_config=runtime_config, opciones=opciones or [])

        print(f"    {pregunta[:50]} ({tipo}): {valor}")
        return self._writer.write(page, valor, container, pregunta=pregunta, tipo=tipo)

    # ── navegación ─────────────────────────────────────────────────────────────

    def _skip_informational_pages(self, page, url: str, runtime_config: dict | None = None, max_iter: int = 3):
        input_selector = (
            '[role="radio"], [role="checkbox"], [role="listbox"], '
            'textarea, input[type="text"], input[type="email"], '
            'input[type="number"], input[type="tel"], input[type="url"], '
            'input[type="date"], input[type="time"], input[type="file"]'
        )
        for _ in range(max_iter):
            try:
                if page.locator(input_selector).count() > 0:
                    return
                if page.locator('span:has-text("Siguiente"), [role="button"]:has-text("Siguiente")').count() == 0:
                    return
                print("    [Google] Página intro sin preguntas -> clic en Siguiente")
                if not click_boton(page, "Siguiente", url, runtime_config=runtime_config):
                    return
                wait_for_form_ready(page, url, runtime_config)
            except Exception:
                return

    # ── helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _get_answerable_items(page, listitems: list, fast_mode: bool) -> list | None:
        if not fast_mode or not listitems:
            return None
        try:
            flags = page.locator('[role="listitem"]').evaluate_all(
                """els => els.map(el => Boolean(
                    el.querySelector('[role="radio"], [role="checkbox"], [role="listbox"], textarea, ' +
                                    'input[type="text"], input[type="email"], input[type="number"], ' +
                                    'input[type="tel"], input[type="url"], input[type="date"], input[type="time"]')
                ))"""
            )
            if isinstance(flags, list):
                return [item for item, ok in zip(listitems, flags) if ok]
        except Exception:
            pass
        return None

    def _matches_expected_page(self, page, pagina_esperada: dict, runtime_config: dict | None = None) -> bool:
        """Confirma avance usando la pregunta esperada cuando la transición es ambigua."""
        wait_for_form_ready(page, "", runtime_config)

        if not pagina_esperada.get("respuestas"):
            input_selector = (
                '[role="radio"], [role="checkbox"], [role="listbox"], '
                'textarea, input[type="text"], input[type="email"], input[type="number"], '
                'input[type="tel"], input[type="url"], input[type="date"], input[type="time"], input[type="file"]'
            )
            try:
                has_inputs = page.locator(input_selector).count() > 0
                has_next = page.locator('span:has-text("Siguiente"), [role="button"]:has-text("Siguiente")').count() > 0
                if not has_inputs and has_next:
                    print("    [Google] Avance confirmado por página informativa.")
                    return True
            except Exception:
                pass

        for respuesta in pagina_esperada.get("respuestas", []):
            pregunta = (respuesta.get("pregunta") or "").strip()
            if not pregunta:
                continue

            try:
                fresh_items = page.locator('[role="listitem"]').all()
            except Exception:
                fresh_items = []

            if self._finder.find(page, pregunta, fresh_items, runtime_config):
                print(f"    [Google] Avance confirmado por estructura: {pregunta[:50]}")
                return True

            try:
                page_text = page.evaluate("document.body ? document.body.innerText : ''") or ""
            except Exception:
                page_text = ""
            if pregunta.lower() in str(page_text).lower():
                print(f"    [Google] Avance confirmado por texto visible: {pregunta[:50]}")
                return True

        return False


def _format_time(segundos: float) -> str:
    if segundos < 60:
        return f"{segundos:.1f}s"
    minutos = int(segundos // 60)
    segs = segundos % 60
    if minutos < 60:
        return f"{minutos}m {segs:.0f}s"
    horas = int(minutos // 60)
    return f"{horas}h {minutos % 60}m {segs:.0f}s"
