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

    def fill_form(self, page, respuesta_generada: dict, url: str, numero: int) -> tuple[bool, float]:
        """Llena un formulario de Google Forms completo."""
        inicio = time.time()
        perfil = respuesta_generada.get("_perfil", "?")
        tendencia = respuesta_generada.get("_tendencia", "?")

        print(f"\n{'='*55}")
        print(f"  ENCUESTA #{numero} | Perfil: {perfil} | Tendencia: {tendencia}")
        print(f"{'='*55}")

        page.goto(url)
        page.wait_for_load_state("networkidle")
        time.sleep(3)

        paginas = respuesta_generada.get("paginas", [])
        submit_clicked = False

        for pag_idx, pagina in enumerate(paginas):
            print(f"  [Pag {pag_idx + 1}/{len(paginas)}]")
            time.sleep(1)

            respuestas = pagina.get("respuestas", [])
            escalas_pendientes = []

            try:
                page.wait_for_selector('[role="listitem"]', timeout=10000)
            except Exception:
                pass
            time.sleep(0.5)

            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(0.5)
            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(0.5)

            listitems = page.locator('[role="listitem"]').all()

            for resp in respuestas:
                tipo = resp["tipo"]
                valor = resp["valor"]
                pregunta = resp["pregunta"]

                if tipo in TIPOS_NO_LLENABLES:
                    print(f"    SKIP ({tipo}): {pregunta[:50]}")
                    continue

                container = self._find_question_container(page, pregunta, listitems)

                if tipo == "opcion_multiple":
                    print(f"    {pregunta[:50]}: {valor}")
                    if str(valor).startswith("Otro"):
                        self._click_otro(page, valor, "radio", container, pregunta=pregunta)
                    else:
                        self._click_opcion(page, valor, "radio", container, pregunta=pregunta)
                    time.sleep(0.5)

                elif tipo == "seleccion_multiple":
                    print(f"    {pregunta[:50]}: {valor}")
                    valores = valor if isinstance(valor, list) else [valor]
                    for item_val in valores:
                        if str(item_val).startswith("Otro"):
                            self._click_otro(page, item_val, "checkbox", container, pregunta=pregunta)
                        else:
                            self._click_opcion(page, item_val, "checkbox", container, pregunta=pregunta)
                        time.sleep(0.3)

                elif tipo == "parrafo":
                    print(f"    {pregunta[:50]}: {str(valor)[:50]}...")
                    self._escribir_parrafo(page, valor, container)
                    time.sleep(0.5)

                elif tipo in ("texto", "numero"):
                    print(f"    {pregunta[:50]}: {valor}")
                    self._escribir_texto(page, valor, container, pregunta=pregunta, tipo=tipo)
                    time.sleep(0.5)

                elif tipo == "escala_lineal":
                    escalas_pendientes.append((valor, container))

                elif tipo == "desplegable":
                    print(f"    {pregunta[:50]}: {valor}")
                    self._seleccionar_dropdown(page, pregunta, valor, container)
                    time.sleep(0.5)

                elif tipo == "fecha":
                    print(f"    {pregunta[:50]}: {valor}")
                    self._llenar_fecha_gforms(page, valor, container)
                    time.sleep(0.5)

                elif tipo == "hora":
                    print(f"    {pregunta[:50]}: {valor}")
                    self._llenar_hora_gforms(page, valor, container)
                    time.sleep(0.5)

                elif tipo in ("matriz", "matriz_checkbox"):
                    print(f"    {pregunta[:50]}: (matriz)")
                    self._llenar_matriz_gforms(page, valor, tipo, container)
                    time.sleep(0.5)

                else:
                    print(f"    {pregunta[:50]} ({tipo}): {valor}")
                    self._escribir_texto(page, valor, container, pregunta=pregunta, tipo=tipo)
                    time.sleep(0.5)

            if escalas_pendientes:
                print(f"    Respondiendo {len(escalas_pendientes)} escalas...")
                self._responder_escalas_scoped(page, escalas_pendientes)

            botones = pagina.get("botones", [])
            if "Siguiente" in botones:
                click_boton(page, "Siguiente", url)
            elif "Enviar" in botones:
                submit_clicked = click_boton(page, "Enviar", url)

        exito = verificar_envio(page, url, submit_clicked=submit_clicked)
        tiempo = time.time() - inicio
        print(f"  {'Enviada' if exito else 'No confirmada'}! {self._formatear_tiempo(tiempo)}")
        return exito, tiempo

    def _find_question_container(self, page, pregunta: str, listitems: list):
        """Encuentra el listitem mas probable usando el texto completo de la pregunta."""
        pregunta_norm = self._normalize_match_text(pregunta, strip_numbering=True)
        if not pregunta_norm:
            return None

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

        if best_item and best_score >= 350:
            self._prepare_scope(best_item)
            return best_item
        return None

    def _click_opcion(self, page, texto_opcion: str, role: str = "radio", container=None, pregunta: str = "") -> bool:
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
        if pregunta:
            try:
                fresh_items = page.locator('[role="listitem"]').all()
                refound = self._find_question_container(page, pregunta, fresh_items)
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
            if self._click_option_in_scope(scope, target, role):
                return True

        if self._click_unique_option_on_page(page, target, role):
            return True

        print(f"      No encontre {role}: '{str(texto_opcion).strip()[:40]}'")
        return False

    def _click_option_in_scope(self, scope, target: str, role: str) -> bool:
        """Busca la opcion dentro de un scope visible y valida la seleccion."""
        self._prepare_scope(scope)

        for _, control in self._find_matching_controls(scope, target, role):
            if self._click_control(control):
                return True

        for _, node in self._find_matching_option_text_nodes(scope, target):
            if self._click_text_node(scope, node, target, role):
                return True

        return False

    def _click_unique_option_on_page(self, page, target: str, role: str) -> bool:
        """Fallback global solo si la opcion aparece una sola vez en toda la pagina."""
        matches = self._find_matching_controls(page, target, role)
        if len(matches) == 1:
            return self._click_control(matches[0][1])
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

    def _click_text_node(self, scope, node, target: str, role: str) -> bool:
        """Hace click sobre texto de opcion y valida que el control asociado quede marcado."""
        candidate_control = None
        try:
            candidate_control = node.locator(
                f'xpath=ancestor-or-self::*[@role="{role}" or (self::input and @type="{role}")][1]'
            )
            if candidate_control.count() > 0 and self._click_control(candidate_control.first):
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
                time.sleep(0.2)
                if self._scope_has_selected_option(scope, target, role):
                    return True
            except Exception:
                continue
        return False

    def _click_control(self, control) -> bool:
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
                time.sleep(0.2)
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

    def _click_otro(self, page, valor: str, role: str, container=None, pregunta: str = "") -> bool:
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
                time.sleep(0.3)
                texto_otro = valor.replace("Otro:", "").replace("Otro", "").strip()
                if texto_otro:
                    inp = scope.locator('input[aria-label="Otro"], input[aria-label="Other response"]').first
                    if inp.is_visible(timeout=1500):
                        inp.fill(texto_otro)
                return True
        except Exception:
            pass
        return self._click_opcion(page, "Otro", role, container, pregunta=pregunta)

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

    def _seleccionar_dropdown(self, page, pregunta: str, valor: str, container=None) -> bool:
        """Dropdown de Google Forms (custom role=listbox)."""
        scope = container if container else page
        self._prepare_scope(scope)
        try:
            for lb in scope.locator('[role="listbox"]').all():
                if lb.is_visible():
                    lb.click()
                    time.sleep(0.5)
                    option = page.locator(f'[role="option"]:has-text("{valor}")').first
                    if option.is_visible(timeout=2000):
                        option.click()
                        return True
                    page.keyboard.press("Escape")
                    time.sleep(0.3)

            if container:
                dropdown = page.locator(f'[role="listbox"]:near(:text("{pregunta[:40]}"))').first
                if dropdown.is_visible(timeout=2000):
                    dropdown.click()
                    time.sleep(0.5)
                    option = page.locator(f'[role="option"]:has-text("{valor}")').first
                    if option.is_visible(timeout=2000):
                        option.click()
                        return True
                    page.keyboard.press("Escape")
            return False
        except Exception:
            return False

    def _llenar_fecha_gforms(self, page, valor: str, container=None) -> bool:
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
                        time.sleep(0.1)
                except Exception:
                    pass
            return True
        except Exception:
            return False

    def _llenar_hora_gforms(self, page, valor: str, container=None) -> bool:
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
                        time.sleep(0.1)
                except Exception:
                    pass
            return True
        except Exception:
            return False

    def _llenar_matriz_gforms(self, page, valor, tipo: str, container=None) -> bool:
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
                            time.sleep(0.2)
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
                        time.sleep(0.2)
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
        if controls:
            random.choice(controls).click()
            return True
        return False

    def _responder_escalas_scoped(self, page, escalas_con_container: list) -> int:
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

                if not seleccionado and radios:
                    radios[random.randint(0, len(radios) - 1)].click()

                respondidas += 1
                time.sleep(0.3)
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
