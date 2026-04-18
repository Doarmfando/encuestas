"""
Llenador especializado para Google Forms.
Usa FillingStrategies compartidas mas selectores especificos de Google Forms.
"""
from difflib import SequenceMatcher
import random
import re
import time
import unicodedata

from app.automation.base_filler import BaseFiller
from app.automation.filling_strategies import FillingStrategies
from app.automation.navigation.button_detector import click_boton, verificar_envio
from app.automation.navigation.waits import wait_for_form_ready
from app.automation.timing import pause_action
from app.constants.question_types import TIPOS_NO_LLENABLES
from app.utils.question_inference import (
    NUMERIC_SHORT_ANSWER_INPUT_SELECTORS,
    SHORT_ANSWER_INPUT_SELECTORS,
    TEXT_SHORT_ANSWER_INPUT_SELECTORS,
    looks_numeric_question,
)

fs = FillingStrategies()


class GoogleFormsFiller(BaseFiller):
    """Llena formularios de Google Forms."""

    def fill_form(
        self,
        page,
        respuesta_generada: dict,
        url: str,
        numero: int,
        runtime_config: dict | None = None,
    ) -> tuple[bool, float]:
        """Llena un formulario de Google Forms completo."""
        inicio = time.time()
        perfil = respuesta_generada.get("_perfil", "?")
        tendencia = respuesta_generada.get("_tendencia", "?")

        print(f"\n{'='*55}")
        print(f"  ENCUESTA #{numero} | Perfil: {perfil} | Tendencia: {tendencia}")
        print(f"{'='*55}")

        page.goto(url, wait_until="domcontentloaded")
        wait_for_form_ready(page, url, runtime_config)

        paginas = respuesta_generada.get("paginas", [])
        submit_clicked = False
        speed_profile = runtime_config.get("speed_profile") if runtime_config else None
        fast_mode = speed_profile in ("turbo", "turbo_plus")
        aggressive_mode = speed_profile == "turbo_plus"

        # Saltar paginas intro puramente informativas solo si la primera pagina
        # de la estructura tiene respuestas (cuando el scraper omitio el intro).
        if paginas and paginas[0].get("respuestas"):
            self._skip_informational_pages(page, url, runtime_config)

        for pag_idx, pagina in enumerate(paginas):
            print(f"  [Pag {pag_idx + 1}/{len(paginas)}]")
            wait_for_form_ready(page, url, runtime_config)
            respuestas = pagina.get("respuestas", [])
            escalas_pendientes = []
            listitems = page.locator('[role="listitem"]').all()
            answerable_items = None
            if fast_mode and listitems:
                try:
                    flags = page.locator('[role="listitem"]').evaluate_all(
                        """els => els.map(el => Boolean(
                            el.querySelector('[role=\"radio\"], [role=\"checkbox\"], [role=\"listbox\"], textarea, ' +
                                            'input[type=\"text\"], input[type=\"email\"], input[type=\"number\"], ' +
                                            'input[type=\"tel\"], input[type=\"url\"], input[type=\"date\"], input[type=\"time\"]')
                        ))"""
                    )
                    if isinstance(flags, list):
                        answerable_items = [item for item, ok in zip(listitems, flags) if ok]
                except Exception:
                    answerable_items = None
            page_failed = False
            failed_questions = []
            answerable_idx = 0

            for resp_idx, resp in enumerate(respuestas):
                tipo = resp["tipo"]
                valor = resp["valor"]
                pregunta = resp["pregunta"]

                if tipo in TIPOS_NO_LLENABLES:
                    print(f"    SKIP ({tipo}): {pregunta[:50]}")
                    continue

                fast_container = None
                if fast_mode and answerable_items and answerable_idx < len(answerable_items):
                    fast_container = answerable_items[answerable_idx]
                answerable_idx += 1
                container = fast_container or self._find_question_container(
                    page, pregunta, listitems, runtime_config=runtime_config
                )
                filled = True

                def _fill_with_container(target_container):
                    if tipo == "opcion_multiple":
                        print(f"    {pregunta[:50]}: {valor}")
                        if str(valor).startswith("Otro"):
                            return self._click_otro(
                                page, valor, "radio", target_container, pregunta=pregunta, runtime_config=runtime_config
                            )
                        return self._click_opcion(
                            page, valor, "radio", target_container, pregunta=pregunta, runtime_config=runtime_config
                        )

                    if tipo == "seleccion_multiple":
                        print(f"    {pregunta[:50]}: {valor}")
                        valores = valor if isinstance(valor, list) else [valor]
                        ok = True
                        for item_val in valores:
                            if str(item_val).startswith("Otro"):
                                current = self._click_otro(
                                    page, item_val, "checkbox", target_container, pregunta=pregunta, runtime_config=runtime_config
                                )
                            else:
                                current = self._click_opcion(
                                    page, item_val, "checkbox", target_container, pregunta=pregunta, runtime_config=runtime_config
                                )
                            ok = ok and current
                            pause_action(runtime_config, multiplier=0.7)
                        return ok

                    if tipo == "parrafo":
                        print(f"    {pregunta[:50]}: {str(valor)[:50]}...")
                        return self._escribir_parrafo(page, valor, target_container)

                    if tipo in ("texto", "numero"):
                        print(f"    {pregunta[:50]}: {valor}")
                        return self._escribir_texto(page, valor, target_container, pregunta=pregunta, tipo=tipo)

                    if tipo == "escala_lineal":
                        escalas_pendientes.append((valor, target_container))
                        return True

                    if tipo == "desplegable":
                        print(f"    {pregunta[:50]}: {valor}")
                        return self._seleccionar_dropdown(page, pregunta, valor, target_container, runtime_config=runtime_config)

                    if tipo == "fecha":
                        print(f"    {pregunta[:50]}: {valor}")
                        return self._llenar_fecha_gforms(page, valor, target_container, runtime_config=runtime_config)

                    if tipo == "hora":
                        print(f"    {pregunta[:50]}: {valor}")
                        return self._llenar_hora_gforms(page, valor, target_container, runtime_config=runtime_config)

                    if tipo in ("matriz", "matriz_checkbox"):
                        print(f"    {pregunta[:50]}: (matriz)")
                        return self._llenar_matriz_gforms(page, valor, tipo, target_container, runtime_config=runtime_config)

                    print(f"    {pregunta[:50]} ({tipo}): {valor}")
                    return self._escribir_texto(page, valor, target_container, pregunta=pregunta, tipo=tipo)

                filled = _fill_with_container(container)
                pause_action(runtime_config)

                if not filled and fast_container is not None and not aggressive_mode:
                    fallback_container = self._find_question_container(
                        page, pregunta, listitems, runtime_config=runtime_config
                    )
                    if fallback_container and fallback_container != container:
                        filled = _fill_with_container(fallback_container)
                        pause_action(runtime_config)

                if not filled:
                    page_failed = True
                    failed_questions.append(pregunta)
                    print(f"      No se pudo completar: {pregunta[:60]}")

            if escalas_pendientes:
                print(f"    Respondiendo {len(escalas_pendientes)} escalas...")
                respondidas = self._responder_escalas_scoped(page, escalas_pendientes, runtime_config=runtime_config)
                if respondidas < len(escalas_pendientes):
                    page_failed = True
                    missing = len(escalas_pendientes) - respondidas
                    failed_questions.append(f"Escalas pendientes ({missing})")

            if page_failed:
                preview = "; ".join(q[:50] for q in failed_questions[:4])
                print(f"    [Google] {len(failed_questions)} respuesta(s) no llenadas")
                if preview:
                    print(f"    [Google] Fallidas: {preview}")
                # Si la página tiene Enviar, intentarlo de todas formas:
                # la pregunta fallida puede ser opcional o un elemento no interactivo
                # (ej: sección de INDICACIONES scrapeada como matriz).
                # Google Forms se encargará de mostrar error si falta algo obligatorio.
                if "Enviar" not in pagina.get("botones", []):
                    break

            botones = pagina.get("botones", [])
            if "Siguiente" in botones:
                advanced = click_boton(page, "Siguiente", url, runtime_config=runtime_config)
                if not advanced:
                    print("    [Google] No se pudo avanzar de pagina. Posible pregunta obligatoria sin responder.")
                    break
                # Saltar posibles paginas intro intermedias solo si la siguiente pagina
                # de la estructura tiene respuestas (el scraper pudo omitir intros).
                next_idx = pag_idx + 1
                if next_idx < len(paginas) and paginas[next_idx].get("respuestas"):
                    self._skip_informational_pages(page, url, runtime_config)
            elif "Enviar" in botones:
                submit_clicked = click_boton(page, "Enviar", url, runtime_config=runtime_config)

        exito = verificar_envio(page, url, submit_clicked=submit_clicked, runtime_config=runtime_config)
        tiempo = time.time() - inicio
        print(f"  {'Enviada' if exito else 'No confirmada'}! {self._formatear_tiempo(tiempo)}")
        return exito, tiempo

    def _skip_informational_pages(
        self,
        page,
        url: str,
        runtime_config: dict | None = None,
        max_iter: int = 3,
    ) -> None:
        """Avanza automaticamente si la pagina actual solo tiene texto informativo.

        Detecta paginas intro/outro (sin inputs respondibles) y hace clic en
        Siguiente hasta llegar a una pagina con preguntas reales.
        """
        input_selector = (
            '[role="radio"], [role="checkbox"], [role="listbox"], '
            'textarea, input[type="text"], input[type="email"], '
            'input[type="number"], input[type="tel"], input[type="url"], '
            'input[type="date"], input[type="time"], input[type="file"]'
        )
        for _ in range(max_iter):
            try:
                has_inputs = page.locator(input_selector).count() > 0
            except Exception:
                return
            if has_inputs:
                return
            try:
                has_next = page.locator(
                    'span:has-text("Siguiente"), [role="button"]:has-text("Siguiente")'
                ).count() > 0
            except Exception:
                return
            if not has_next:
                return
            print("    [Google] Pagina intro sin preguntas -> clic en Siguiente")
            advanced = click_boton(page, "Siguiente", url, runtime_config=runtime_config)
            if not advanced:
                return
            wait_for_form_ready(page, url, runtime_config)

    def _find_question_container(
        self,
        page,
        pregunta: str,
        listitems: list,
        runtime_config: dict | None = None,
    ):
        """Encuentra el listitem mas probable usando el texto completo de la pregunta."""
        pregunta_norm = self._normalize_match_text(pregunta, strip_numbering=True)
        if not pregunta_norm:
            return None

        best_item, best_score = self._best_question_candidate(listitems, pregunta_norm)
        if best_item and best_score >= 350:
            self._prepare_scope(best_item)
            return best_item

        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            pause_action(runtime_config, multiplier=0.8)
            page.evaluate("window.scrollTo(0, 0)")
            pause_action(runtime_config, multiplier=0.8)
            fresh_items = page.locator('[role="listitem"]').all()
            best_item, best_score = self._best_question_candidate(fresh_items, pregunta_norm)
            if best_item and best_score >= 350:
                self._prepare_scope(best_item)
                return best_item
        except Exception:
            pass

        return None

    def _best_question_candidate(self, listitems: list, pregunta_norm: str):
        best_item = None
        best_score = 0
        for item in listitems:
            try:
                score = self._score_question_candidate(item.inner_text(timeout=1200), pregunta_norm)
                if score > best_score:
                    best_score = score
                    best_item = item
            except Exception:
                continue
        return best_item, best_score

    def _click_opcion(
        self,
        page,
        texto_opcion: str,
        role: str = "radio",
        container=None,
        pregunta: str = "",
        runtime_config: dict | None = None,
    ) -> bool:
        """Click en radio o checkbox validando que quede marcado en el contenedor correcto."""
        target = self._normalize_match_text(texto_opcion)
        if not target:
            print(f"      Opcion vacia para {role}")
            return False

        scopes = []
        if container:
            scopes.append(container)
        else:
            scopes.append(page)

        refound = None
        allow_refind = True
        if runtime_config and runtime_config.get("speed_profile") in ("turbo", "turbo_plus"):
            allow_refind = False
        if pregunta and allow_refind:
            try:
                fresh_items = page.locator('[role="listitem"]').all()
                refound = self._find_question_container(page, pregunta, fresh_items, runtime_config=runtime_config)
            except Exception:
                refound = None

        if refound and (not container or refound != container):
            scopes.append(refound)

        tried_keys = set()
        for scope in scopes:
            scope_key = id(scope)
            if scope_key in tried_keys:
                continue
            tried_keys.add(scope_key)
            if self._click_option_in_scope(scope, target, role, runtime_config=runtime_config):
                return True

        if self._click_unique_option_on_page(page, target, role, runtime_config=runtime_config):
            return True

        print(f"      No encontre {role}: '{str(texto_opcion).strip()[:40]}'")
        return False

    def _click_option_in_scope(self, scope, target: str, role: str, runtime_config: dict | None = None) -> bool:
        """Busca la opcion dentro de un scope visible y valida la seleccion."""
        self._prepare_scope(scope)

        for _, control in self._find_matching_controls(scope, target, role):
            if self._click_control(control, runtime_config=runtime_config):
                return True

        for _, node in self._find_matching_option_text_nodes(scope, target):
            if self._click_text_node(scope, node, target, role, runtime_config=runtime_config):
                return True

        return False

    def _click_unique_option_on_page(self, page, target: str, role: str, runtime_config: dict | None = None) -> bool:
        """Fallback global solo si la opcion aparece una sola vez en toda la pagina."""
        matches = self._find_matching_controls(page, target, role)
        if len(matches) == 1:
            return self._click_control(matches[0][1], runtime_config=runtime_config)
        return False

    def _find_matching_controls(self, scope, target: str, role: str) -> list[tuple[int, object]]:
        """Obtiene controles candidatos ordenados por score de similitud."""
        matches = []
        try:
            controls = scope.locator(f'[role="{role}"], input[type="{role}"]').all()
        except Exception:
            return matches

        for control in controls:
            try:
                score = self._score_option_candidate(self._collect_control_labels(control), target)
                if score > 0:
                    matches.append((score, control))
            except Exception:
                continue

        matches.sort(key=lambda item: item[0], reverse=True)
        return matches

    def _find_matching_option_text_nodes(self, scope, target: str) -> list[tuple[int, object]]:
        """Busca nodos de texto cortos que coincidan con la opcion dentro del contenedor."""
        matches = []
        try:
            nodes = scope.locator("label, span, div").all()
        except Exception:
            return matches

        for node in nodes:
            try:
                text = node.inner_text(timeout=200).strip()
            except Exception:
                continue

            if not text or len(text) > 80:
                continue

            score = self._score_option_candidate([text], target)
            if score > 0:
                matches.append((score, node))

        matches.sort(key=lambda item: item[0], reverse=True)
        return matches[:8]

    def _click_text_node(self, scope, node, target: str, role: str, runtime_config: dict | None = None) -> bool:
        """Hace click sobre texto de opcion y valida que el control asociado quede marcado."""
        candidate_control = None
        try:
            candidate_control = node.locator(
                f'xpath=ancestor-or-self::*[@role="{role}" or (self::input and @type="{role}")][1]'
            )
            if candidate_control.count() > 0 and self._click_control(candidate_control.first, runtime_config=runtime_config):
                return True
        except Exception:
            pass

        for click_action in (
            lambda: node.click(),
            lambda: node.click(force=True),
            lambda: node.evaluate(
                """el => {
                    const target = el.closest('[role="radio"], [role="checkbox"], label, div, span') || el;
                    target.scrollIntoView({block: "center", inline: "nearest"});
                    target.click();
                }"""
            ),
        ):
            try:
                click_action()
                pause_action(runtime_config, multiplier=0.7)
                if self._scope_has_selected_option(scope, target, role):
                    return True
            except Exception:
                continue
        return False

    def _click_control(self, control, runtime_config: dict | None = None) -> bool:
        """Intenta varias formas de click y verifica que el control quede activo."""
        if self._is_control_selected(control):
            return True

        for click_action in (
            lambda: control.click(),
            lambda: control.click(force=True),
            lambda: control.evaluate(
                """el => {
                    el.scrollIntoView({block: "center", inline: "nearest"});
                    el.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
                    el.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
                    el.click();
                    el.dispatchEvent(new Event('input', {bubbles: true}));
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                }"""
            ),
        ):
            try:
                control.scroll_into_view_if_needed()
            except Exception:
                pass

            try:
                click_action()
                pause_action(runtime_config, multiplier=0.7)
                if self._is_control_selected(control):
                    return True
            except Exception:
                continue

        return False

    def _scope_has_selected_option(self, scope, target: str, role: str) -> bool:
        """Comprueba si dentro del scope hay una opcion seleccionada que coincida."""
        try:
            selected = scope.locator(
                f'[role="{role}"][aria-checked="true"], input[type="{role}"]:checked'
            ).all()
        except Exception:
            return False

        for control in selected:
            try:
                if self._score_option_candidate(self._collect_control_labels(control), target) >= 1000:
                    return True
            except Exception:
                continue
        return False

    def _collect_control_labels(self, control) -> list[str]:
        """Extrae textos cortos relevantes del control y sus wrappers inmediatos."""
        try:
            texts = control.evaluate(
                """el => {
                    const out = [];
                    const add = (value) => {
                        const text = (value || '').toString().trim();
                        if (text && !out.includes(text)) out.push(text);
                    };
                    add(el.getAttribute && el.getAttribute('aria-label'));
                    add(el.getAttribute && el.getAttribute('data-value'));
                    add(el.getAttribute && el.getAttribute('value'));
                    add(el.textContent);
                    const parent = el.parentElement;
                    const label = el.closest('label');
                    const wrapper = el.closest('[role="radio"], [role="checkbox"]');
                    [parent, label, wrapper].forEach(node => {
                        if (!node || node === el) return;
                        add(node.getAttribute && node.getAttribute('aria-label'));
                        add(node.getAttribute && node.getAttribute('data-value'));
                        add(node.textContent);
                    });
                    return out.slice(0, 8);
                }"""
            )
            return texts if isinstance(texts, list) else []
        except Exception:
            return []

    def _score_option_candidate(self, values: list[str], target: str) -> int:
        """Puntua una opcion evitando matches ambiguos como 'Nunca' vs 'Casi nunca'."""
        best = 0
        target_norm = self._normalize_match_text(target)
        for value in values:
            candidate = self._normalize_match_text(value)
            if not candidate:
                continue
            if candidate == target_norm:
                best = max(best, 1200)
                continue

            ratio = SequenceMatcher(None, target_norm, candidate).ratio()
            if ratio >= 0.97:
                best = max(best, int(ratio * 1000))

        return best

    def _score_question_candidate(self, candidate_text: str, target: str) -> int:
        """Puntua un listitem para elegir la pregunta correcta aun con prefijos repetidos."""
        candidate = self._normalize_match_text(candidate_text, strip_numbering=True)
        if not candidate:
            return 0

        lines = [
            self._normalize_match_text(line, strip_numbering=True)
            for line in str(candidate_text or "").splitlines()
            if line.strip()
        ]
        heading = lines[0] if lines else ""

        score = 0
        if heading == target:
            score += 5000
        if candidate == target:
            score += 4500
        if heading and target in heading:
            score += 3500 + min(len(target), 400)
        if target in candidate:
            score += 3000 + min(len(target), 400)

        sample = heading or candidate[: max(len(target) * 2, 180)]
        score += int(SequenceMatcher(None, target, sample).ratio() * 1200)

        tokens = [tok for tok in re.findall(r"[a-z0-9]+", target) if len(tok) >= 4]
        if tokens:
            common = sum(1 for tok in tokens if tok in candidate)
            coverage = common / len(tokens)
            score += common * 140
            score += int(coverage * 800)
            if common == len(tokens):
                score += 900

        return score

    @staticmethod
    def _normalize_match_text(value: str, strip_numbering: bool = False) -> str:
        """Normaliza texto para comparar preguntas y opciones sin acentos ni puntuacion."""
        text = str(value or "").replace("\u00a0", " ")
        if strip_numbering:
            text = re.sub(r"^\s*\d+\s*[\.\)\-:]+\s*", "", text)
        text = text.replace("“", '"').replace("”", '"').replace("’", "'")
        text = unicodedata.normalize("NFKD", text)
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        text = re.sub(r"[*]+", " ", text.lower())
        text = re.sub(r"[^\w\s]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _prepare_scope(scope) -> None:
        """Hace visible el contenedor antes de interactuar con sus controles."""
        try:
            scope.scroll_into_view_if_needed()
            time.sleep(0.15)
        except Exception:
            pass

    @staticmethod
    def _is_control_selected(control) -> bool:
        """Detecta si un radio/checkbox ya esta marcado."""
        try:
            aria_checked = (control.get_attribute("aria-checked") or "").lower()
            if aria_checked == "true":
                return True
            return bool(control.evaluate("el => Boolean(el.checked)"))
        except Exception:
            return False

    def _click_otro(
        self,
        page,
        valor: str,
        role: str,
        container=None,
        pregunta: str = "",
        runtime_config: dict | None = None,
    ) -> bool:
        """Selecciona opcion Otro y escribe texto."""
        scope = container if container else page
        self._prepare_scope(scope)
        try:
            if role == "radio":
                otro = scope.locator(
                    '[data-value="__other_option__"], [aria-label="Otro"], [aria-label="Other"]'
                ).first
            else:
                otro = scope.locator(
                    '[role="checkbox"][aria-label="Otro"], [role="checkbox"][aria-label="Other"]'
                ).first

            if otro.is_visible(timeout=2000):
                otro.click()
                pause_action(runtime_config, multiplier=0.8)
                texto_otro = valor.replace("Otro:", "").replace("Otro", "").strip()
                if texto_otro:
                    inp = scope.locator('input[aria-label="Otro"], input[aria-label="Other response"]').first
                    if inp.is_visible(timeout=1500):
                        inp.fill(texto_otro)
                return True
        except Exception:
            pass
        return self._click_opcion(page, "Otro", role, container, pregunta=pregunta, runtime_config=runtime_config)

    def _escribir_texto(self, page, valor, container=None, pregunta: str = "", tipo: str = "texto") -> bool:
        """Escribe en una respuesta corta validando que quede en el input correcto."""
        scope = container if container else page
        self._prepare_scope(scope)
        try:
            field_hints = self._collect_input_hints(scope)
            prefer_numeric = tipo == "numero" or looks_numeric_question(pregunta, field_hints)
            selector_groups = [
                NUMERIC_SHORT_ANSWER_INPUT_SELECTORS if prefer_numeric else TEXT_SHORT_ANSWER_INPUT_SELECTORS,
                TEXT_SHORT_ANSWER_INPUT_SELECTORS if prefer_numeric else NUMERIC_SHORT_ANSWER_INPUT_SELECTORS,
                SHORT_ANSWER_INPUT_SELECTORS,
            ]

            usados = set()
            for selectors in selector_groups:
                key = tuple(selectors)
                if key in usados:
                    continue
                usados.add(key)
                if self._fill_short_answer_with_selectors(scope, valor, selectors):
                    return True

            if container:
                return self._escribir_texto(page, valor, None, pregunta=pregunta, tipo=tipo)

            print("      No encontre campo de respuesta corta")
            return False
        except Exception as e:
            print(f"      Error texto: {e}")
            return False

    def _escribir_parrafo(self, page, valor, container=None) -> bool:
        """Escribe en un textarea vacio visible."""
        scope = container if container else page
        self._prepare_scope(scope)
        try:
            for ta in scope.locator("textarea").all():
                if ta.is_visible() and not ta.input_value():
                    ta.fill(str(valor))
                    return True
            return self._escribir_texto(page, valor, container, tipo="parrafo")
        except Exception:
            return False

    def _seleccionar_dropdown(self, page, pregunta: str, valor: str, container=None, runtime_config: dict | None = None) -> bool:
        """Dropdown de Google Forms (custom role=listbox)."""
        scope = container if container else page
        self._prepare_scope(scope)
        target = self._normalize_match_text(valor)

        dropdowns = []
        try:
            dropdowns.extend(scope.locator('[role="listbox"]').all())
        except Exception:
            pass

        if container and not dropdowns:
            try:
                dropdown = page.locator(f'[role="listbox"]:near(:text("{pregunta[:40]}"))').first
                if dropdown and dropdown.is_visible(timeout=400):
                    dropdowns.append(dropdown)
            except Exception:
                pass

        tried = set()
        for lb in dropdowns:
            if id(lb) in tried:
                continue
            tried.add(id(lb))

            try:
                if not lb.is_visible(timeout=500):
                    continue
            except Exception:
                continue

            if self._dropdown_has_value(page, lb, target):
                return True

            if not self._open_dropdown(page, lb):
                continue

            pause_action(runtime_config, multiplier=1.0)
            if self._click_dropdown_option(page, lb, target, runtime_config=runtime_config):
                pause_action(runtime_config, multiplier=0.8)
                if self._dropdown_has_value(page, lb, target):
                    return True
                if container:
                    try:
                        for refreshed in container.locator('[role="listbox"]').all():
                            if self._dropdown_has_value(page, refreshed, target):
                                return True
                    except Exception:
                        pass

            try:
                page.keyboard.press("Escape")
                pause_action(runtime_config, multiplier=0.6)
            except Exception:
                pass

        return False

    def _open_dropdown(self, page, listbox) -> bool:
        for action in (
            lambda: listbox.click(),
            lambda: listbox.click(force=True),
            lambda: listbox.evaluate(
                """el => {
                    el.scrollIntoView({block: "center", inline: "nearest"});
                    el.click();
                }"""
            ),
        ):
            try:
                listbox.scroll_into_view_if_needed()
            except Exception:
                pass
            try:
                action()
                expanded = (listbox.get_attribute("aria-expanded") or "").lower()
                if expanded == "true" or self._visible_dropdown_options(page):
                    return True
            except Exception:
                continue
        return False

    def _click_dropdown_option(self, page, listbox, target: str, runtime_config: dict | None = None) -> bool:
        matches = []
        try:
            options = page.locator('[role="option"]').all()
        except Exception:
            return False

        for option in options:
            try:
                if hasattr(option, "is_visible") and not option.is_visible(timeout=200):
                    continue
                text = option.inner_text(timeout=300).strip()
            except Exception:
                continue

            score = self._score_option_candidate([text], target)
            if score > 0:
                matches.append((score, option))

        matches.sort(key=lambda item: item[0], reverse=True)
        for _, option in matches:
            try:
                option.scroll_into_view_if_needed()
            except Exception:
                pass

            for action, confirm_with_enter in (
                (lambda: option.click(), False),
                (lambda: option.click(force=True), False),
                (lambda: option.evaluate(
                    """el => {
                        el.scrollIntoView({block: "center", inline: "nearest"});
                        el.click();
                    }"""
                ), False),
                (lambda: option.focus(), True),
                (lambda: option.hover(), True),
            ):
                try:
                    action()
                    if confirm_with_enter:
                        page.keyboard.press("Enter")
                    pause_action(runtime_config, multiplier=0.6)
                    if self._dropdown_has_value(page, listbox, target):
                        return True
                except Exception:
                    continue

        if matches and self._select_dropdown_option_with_keyboard(page, listbox, matches, target, runtime_config):
            return True
        return False

    def _dropdown_has_value(self, page, listbox, target: str) -> bool:
        try:
            values = listbox.evaluate(
                """el => {
                    const out = [];
                    const add = (value) => {
                        const text = (value || '').toString().trim();
                        if (text && !out.includes(text)) out.push(text);
                    };
                    add(el.getAttribute && el.getAttribute('aria-label'));
                    add(el.getAttribute && el.getAttribute('data-value'));
                    add((el.innerText || el.textContent || '').split('\n')[0]);
                    return out.slice(0, 8);
                }"""
            )
        except Exception:
            values = []

        try:
            selected_options = page.locator('[role="option"][aria-selected="true"], [role="option"][aria-checked="true"]').all()
            for option in selected_options:
                try:
                    values.append(option.inner_text(timeout=200).strip())
                except Exception:
                    continue
        except Exception:
            pass

        placeholder_tokens = {"elige", "choose", "select"}
        for value in values if isinstance(values, list) else []:
            normalized = self._normalize_match_text(value)
            if not normalized or normalized in placeholder_tokens:
                continue
            if normalized == target:
                return True
        return False

    @staticmethod
    def _visible_dropdown_options(page) -> int:
        try:
            options = page.locator('[role="option"]').all()
        except Exception:
            return 0

        visible = 0
        for option in options:
            try:
                if hasattr(option, "is_visible") and option.is_visible(timeout=150):
                    visible += 1
            except Exception:
                continue
        return visible

    def _select_dropdown_option_with_keyboard(
        self,
        page,
        listbox,
        matches,
        target: str,
        runtime_config: dict | None = None,
    ) -> bool:
        try:
            visible_options = []
            for option in page.locator('[role="option"]').all():
                try:
                    if hasattr(option, "is_visible") and not option.is_visible(timeout=150):
                        continue
                    visible_options.append(option)
                except Exception:
                    continue

            if not visible_options:
                return False

            best_option = matches[0][1]
            target_idx = None
            for idx, option in enumerate(visible_options):
                if option == best_option:
                    target_idx = idx
                    break
            if target_idx is None:
                return False

            try:
                listbox.focus()
            except Exception:
                listbox.click(force=True)

            page.keyboard.press("Home")
            pause_action(runtime_config, multiplier=0.4)
            for _ in range(target_idx):
                page.keyboard.press("ArrowDown")
                pause_action(runtime_config, multiplier=0.25)
            page.keyboard.press("Enter")
            pause_action(runtime_config, multiplier=0.6)
            return self._dropdown_has_value(page, listbox, target)
        except Exception:
            return False

    def _llenar_fecha_gforms(self, page, valor: str, container=None, runtime_config: dict | None = None) -> bool:
        """Google Forms usa inputs separados para dia, mes y anio."""
        scope = container if container else page
        self._prepare_scope(scope)
        partes = FillingStrategies._parse_date(valor)
        if not partes:
            return self._escribir_texto(page, valor, container, tipo="fecha")
        dia, mes, anio = partes

        try:
            for sel, val in [
                ('[aria-label*="Dia" i], [aria-label*="Día" i], [aria-label*="Day" i]', str(dia)),
                ('[aria-label*="Mes" i], [aria-label*="Month" i]', str(mes)),
                ('[aria-label*="Ano" i], [aria-label*="Año" i], [aria-label*="Year" i]', str(anio)),
            ]:
                try:
                    el = scope.locator(sel).first
                    if el.is_visible(timeout=1000):
                        el.fill(val)
                        pause_action(runtime_config, multiplier=0.6)
                except Exception:
                    pass
            return True
        except Exception:
            return False

    def _llenar_hora_gforms(self, page, valor: str, container=None, runtime_config: dict | None = None) -> bool:
        """Google Forms usa inputs separados para hora y minuto."""
        scope = container if container else page
        self._prepare_scope(scope)
        partes = str(valor).split(":")
        hora = partes[0].strip() if partes else "12"
        minuto = partes[1].strip() if len(partes) > 1 else "00"

        try:
            for sel, val in [
                ('[aria-label*="Hora" i], [aria-label*="Hour" i]', hora),
                ('[aria-label*="Minuto" i], [aria-label*="Minute" i]', minuto),
            ]:
                try:
                    el = scope.locator(sel).first
                    if el.is_visible(timeout=1000):
                        el.fill(val)
                        pause_action(runtime_config, multiplier=0.6)
                except Exception:
                    pass
            return True
        except Exception:
            return False

    def _llenar_matriz_gforms(self, page, valor, tipo: str, container=None, runtime_config: dict | None = None) -> bool:
        """Google Forms matrices usan radiogroups."""
        scope = container if container else page
        self._prepare_scope(scope)
        try:
            rows = scope.locator('[role="radiogroup"], [role="group"]').all()
            if not rows:
                return False

            if isinstance(valor, dict):
                for row in rows:
                    row_label = (row.get_attribute("aria-label") or row.inner_text().split("\n")[0]).strip()
                    for fila_key, col_val in valor.items():
                        if fila_key.lower() in row_label.lower() or row_label.lower() in fila_key.lower():
                            role = "checkbox" if tipo == "matriz_checkbox" else "radio"
                            if isinstance(col_val, list):
                                for cv in col_val:
                                    self._click_en_grupo(row, str(cv), role)
                            else:
                                self._click_en_grupo(row, str(col_val), role)
                            pause_action(runtime_config, multiplier=0.7)
                            break
            elif isinstance(valor, list):
                for idx, val in enumerate(valor):
                    if idx < len(rows):
                        role = "checkbox" if tipo == "matriz_checkbox" else "radio"
                        if isinstance(val, list):
                            for item_val in val:
                                self._click_en_grupo(rows[idx], str(item_val), role)
                        else:
                            self._click_en_grupo(rows[idx], str(val), role)
                        pause_action(runtime_config, multiplier=0.7)
            return True
        except Exception as e:
            print(f"      Error matriz: {e}")
            return False

    def _click_en_grupo(self, row, valor: str, role: str) -> bool:
        """Click en control dentro de un grupo de matriz."""
        controls = row.locator(f'[role="{role}"]').all()
        for ctrl in controls:
            label = ctrl.get_attribute("aria-label") or ""
            if valor.lower() in label.lower() or label.lower() in valor.lower():
                ctrl.click()
                return True
        if valor.isdigit():
            idx = int(valor) - 1
            if 0 <= idx < len(controls):
                controls[idx].click()
                return True
        return False

    def _responder_escalas_scoped(
        self,
        page,
        escalas_con_container: list,
        runtime_config: dict | None = None,
    ) -> int:
        """Responde escalas Likert usando contenedores ya identificados."""
        respondidas = 0
        for valor, container in escalas_con_container:
            try:
                scope = container if container else page
                radios = scope.locator('[role="radio"]').all()
                if not radios:
                    continue

                respuesta = str(valor).lower()
                seleccionado = False

                for radio in radios:
                    aria = (radio.get_attribute("aria-label") or "").lower()
                    if respuesta in aria:
                        radio.click()
                        seleccionado = True
                        break

                if not seleccionado:
                    for radio in radios:
                        dv = (radio.get_attribute("data-value") or "").lower()
                        if dv == respuesta:
                            radio.click()
                            seleccionado = True
                            break

                if not seleccionado and respuesta.isdigit():
                    target_idx = int(respuesta) - 1
                    if 0 <= target_idx < len(radios):
                        radios[target_idx].click()
                        seleccionado = True

                if seleccionado:
                    respondidas += 1
                    pause_action(runtime_config, multiplier=0.8)
            except Exception:
                continue

        print(f"    Respondidas {respondidas} escalas")
        return respondidas

    @staticmethod
    def _formatear_tiempo(segundos: float) -> str:
        if segundos < 60:
            return f"{segundos:.1f}s"
        minutos = int(segundos // 60)
        segs = segundos % 60
        if minutos < 60:
            return f"{minutos}m {segs:.0f}s"
        horas = int(minutos // 60)
        mins = minutos % 60
        return f"{horas}h {mins}m {segs:.0f}s"

    def _fill_short_answer_with_selectors(self, scope, valor, selectors: list[str]) -> bool:
        """Intenta llenar el mejor input visible para una respuesta corta."""
        valor_str = str(valor).strip()
        try:
            inputs = scope.locator(", ".join(selectors))
            overwrite_candidates = []
            for idx in range(inputs.count()):
                inp = inputs.nth(idx)
                try:
                    if not inp.is_visible(timeout=500) or self._is_temporal_input(inp):
                        continue
                    current_value = (inp.input_value() or "").strip()
                    if self._matches_input_value(current_value, valor_str):
                        return True
                    if current_value:
                        overwrite_candidates.append(inp)
                        continue
                    if self._try_fill_input(inp, valor_str):
                        return True
                except Exception:
                    continue

            for inp in overwrite_candidates:
                if self._try_fill_input(inp, valor_str):
                    return True
        except Exception:
            pass
        return False

    def _try_fill_input(self, inp, valor: str) -> bool:
        """Llena un input y valida que el valor se haya quedado."""
        try:
            inp.scroll_into_view_if_needed()
            inp.click()
        except Exception:
            pass

        try:
            inp.fill("")
        except Exception:
            pass

        try:
            inp.fill(valor)
        except Exception:
            try:
                inp.evaluate(
                    """(el, value) => {
                        el.focus();
                        el.value = "";
                        el.dispatchEvent(new Event("input", {bubbles: true}));
                        el.value = value;
                        el.dispatchEvent(new Event("input", {bubbles: true}));
                        el.dispatchEvent(new Event("change", {bubbles: true}));
                    }""",
                    valor,
                )
            except Exception:
                return False

        try:
            inp.dispatch_event("input")
            inp.dispatch_event("change")
        except Exception:
            pass

        try:
            final_value = (inp.input_value() or "").strip()
        except Exception:
            final_value = ""

        return self._matches_input_value(final_value, valor) or bool(final_value)

    @staticmethod
    def _matches_input_value(actual: str, expected: str) -> bool:
        """Compara el valor escrito tolerando formatos numericos."""
        actual = str(actual or "").strip()
        expected = str(expected or "").strip()

        if actual == expected:
            return True
        if actual.replace(" ", "") == expected.replace(" ", ""):
            return True

        expected_digits = re.sub(r"\D", "", expected)
        actual_digits = re.sub(r"\D", "", actual)
        if expected_digits and actual_digits and expected_digits == actual_digits:
            return True

        return False

    def _collect_input_hints(self, scope, max_inputs: int = 3) -> str:
        """Recoge attrs del campo para decidir si conviene tratarlo como numero."""
        hints = []
        try:
            inputs = scope.locator(", ".join(SHORT_ANSWER_INPUT_SELECTORS))
            total = min(inputs.count(), max_inputs)
            for idx in range(total):
                el = inputs.nth(idx)
                attrs = []
                for attr in ("type", "inputmode", "pattern", "aria-label", "placeholder", "min", "max", "step", "role"):
                    value = el.get_attribute(attr) or ""
                    if value:
                        attrs.append(f"{attr}={value}")
                if attrs:
                    hints.append(" ".join(attrs))
        except Exception:
            pass
        return " | ".join(hints)

    @staticmethod
    def _is_temporal_input(locator) -> bool:
        """Evita tratar subcampos de fecha u hora como respuesta corta comun."""
        try:
            input_type = (locator.get_attribute("type") or "").lower()
            if input_type in ("date", "time"):
                return True
            attrs = " ".join([
                locator.get_attribute("aria-label") or "",
                locator.get_attribute("placeholder") or "",
            ]).lower()
            return any(token in attrs for token in (
                "dia", "día", "day", "mes", "month", "ano", "año", "year", "hora", "hour", "minuto", "minute"
            ))
        except Exception:
            return False
