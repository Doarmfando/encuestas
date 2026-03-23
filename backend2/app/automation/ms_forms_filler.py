"""
Llenador específico para Microsoft Forms.
Usa FillingStrategies compartidas + selectores específicos de MS Forms.
"""
import re
import unicodedata
from difflib import SequenceMatcher

from app.automation.filling_strategies import FillingStrategies
from app.automation.navigation.waits import capture_page_state, wait_for_form_ready, wait_for_post_action, wait_for_submission_signal
from app.automation.timing import pause_action
from app.constants.question_types import TIPOS_NO_LLENABLES

# Selectores específicos de MS Forms
MS_TEXT_SELECTORS = [
    'input[aria-label="Single line text"]',
    'input[role="textbox"]',
    '[role="textbox"] input',
    'input[type="text"]',
    '[contenteditable="true"]',
    'input:not([type="radio"]):not([type="checkbox"]):not([type="hidden"])',
]
MS_TEXTAREA_SELECTORS = [
    'textarea',
    'div[role="textbox"]',
    '[contenteditable="true"]',
    'input[aria-label="Long answer text"]',
]
MS_NUMBER_SELECTORS = [
    'input[type="number"]',
    'input[inputmode="numeric"]',
    'input[aria-label*="number" i]',
    'input[aria-label*="número" i]',
    'input[type="text"]',
    'input:not([type="radio"]):not([type="checkbox"]):not([type="hidden"])',
]
MS_CONTAINER_SELECTORS = [
    '#question-list [data-automation-id*="question"]',
    '#question-list [class*="question-container"]',
    '#question-list [class*="office-form-question"]',
    '#question-list fieldset',
    '#question-list [role="group"]',
    '#question-list > div',
]

fs = FillingStrategies()


class MSFormsFiller:
    """Llena formularios de Microsoft Forms usando selectores nativos."""

    def fill_page(self, page, respuestas: list, runtime_config: dict | None = None):
        """Llena todas las respuestas de una página de MS Forms."""
        result = {
            "ok": False,
            "filled": 0,
            "failed": 0,
            "failed_questions": [],
        }

        if not wait_for_form_ready(page, page.url, runtime_config):
            print("    [MS] No se encontró #question-list")
            result["failed"] = 1
            result["failed_questions"].append("__page__")
            return result

        for resp_idx, resp in enumerate(respuestas):
            tipo = resp["tipo"]
            valor = resp["valor"]
            pregunta = resp["pregunta"]

            container = self._find_question(page, resp_idx, pregunta)
            if not container:
                print(f"    [MS] No encontré: {pregunta[:50]}")
                result["failed"] += 1
                result["failed_questions"].append(pregunta)
                continue

            filled = self._fill_element(container, page, tipo, valor, pregunta, runtime_config=runtime_config)

            if filled:
                print(f"    OK: {pregunta[:50]}")
                result["filled"] += 1
            else:
                print(f"    FALLÓ: {pregunta[:50]}")
                result["failed"] += 1
                result["failed_questions"].append(pregunta)

            pause_action(runtime_config)

        result["ok"] = result["failed"] == 0
        return result

    def click_submit(self, page, url: str = "", runtime_config: dict | None = None) -> bool:
        """Click en botón Enviar/Submit de MS Forms."""
        return self._click_submit_button(page, url=url, runtime_config=runtime_config)

    def click_next(self, page, url: str = "", runtime_config: dict | None = None) -> bool:
        """Click en botón Siguiente/Next de MS Forms."""
        before_state = capture_page_state(page, url)
        for sel in ['button:has-text("Siguiente")', 'button:has-text("Next")', 'button[data-automation-id="nextButton"]']:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=2000):
                    btn.click()
                    wait_for_post_action(page, before_state, url, runtime_config, after_submit=False)
                    return True
            except Exception:
                continue
        return False

    # ========== ENCONTRAR PREGUNTA ==========

    def _find_question(self, page, expected_idx: int, pregunta: str):
        """Encuentra la div de la pregunta en #question-list."""
        candidates = self._visible_question_containers(page)
        if not candidates:
            return None

        pregunta_norm = self._normalize_question(pregunta)
        best_container = None
        best_score = 0

        for container in candidates:
            try:
                text = container.inner_text(timeout=1500)
            except Exception:
                continue

            score = self._score_question_match(pregunta_norm, self._normalize_question(text))
            if score > best_score:
                best_score = score
                best_container = container

        if best_container and best_score >= 250:
            return best_container

        if expected_idx < len(candidates):
            return candidates[expected_idx]
        return None

    def _visible_question_containers(self, page):
        """Retorna contenedores visibles con controles rellenables."""
        for selector in MS_CONTAINER_SELECTORS:
            try:
                locator = page.locator(selector)
                candidates = []
                for idx in range(locator.count()):
                    container = locator.nth(idx)
                    try:
                        if not container.is_visible(timeout=300):
                            continue
                        if self._container_has_fillable_controls(container):
                            candidates.append(container)
                    except Exception:
                        continue
                if candidates:
                    return candidates
            except Exception:
                continue
        return []

    @staticmethod
    def _container_has_fillable_controls(container) -> bool:
        selectors = (
            'input:not([type="hidden"]), textarea, select, [role="radio"], [role="checkbox"], '
            '[role="combobox"], [role="listbox"], [class*="rating"] button, button[aria-posinset]'
        )
        try:
            return container.locator(selectors).count() > 0
        except Exception:
            return False

    @staticmethod
    def _normalize_question(value: str) -> str:
        text = unicodedata.normalize("NFKD", str(value or ""))
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        text = re.sub(r"[^\w\s]", " ", text.lower())
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _score_question_match(target: str, candidate: str) -> int:
        if not target or not candidate:
            return 0
        if target == candidate:
            return 2000
        score = 0
        if target in candidate:
            score += 1200 + min(len(target), 200)
        ratio = SequenceMatcher(None, target, candidate[: max(len(target) * 2, 120)]).ratio()
        score += int(ratio * 600)
        target_tokens = [tok for tok in target.split() if len(tok) >= 4]
        if target_tokens:
            overlap = sum(1 for tok in target_tokens if tok in candidate)
            score += overlap * 120
        return score

    # ========== ROUTER DE TIPOS ==========

    def _fill_element(
        self,
        container,
        page,
        tipo: str,
        valor,
        pregunta: str,
        runtime_config: dict | None = None,
    ) -> bool:
        """Redirige al método correcto según el tipo de pregunta."""
        try:
            if tipo in TIPOS_NO_LLENABLES:
                print(f"    [MS] SKIP ({tipo}): {pregunta[:40]}")
                return True

            if tipo == "texto":
                return fs.fill_text(container, valor, MS_TEXT_SELECTORS, runtime_config=runtime_config)

            elif tipo == "numero":
                return fs.fill_text(container, valor, MS_NUMBER_SELECTORS, runtime_config=runtime_config)

            elif tipo == "parrafo":
                return fs.fill_textarea(container, valor, MS_TEXTAREA_SELECTORS, runtime_config=runtime_config)

            elif tipo == "opcion_multiple":
                return fs.click_option_by_text(
                    container, page, str(valor), "radio", use_js_click=True, runtime_config=runtime_config
                )

            elif tipo == "seleccion_multiple":
                return fs.click_multiple_options(
                    container, page, valor, "checkbox", use_js_click=True, runtime_config=runtime_config
                )

            elif tipo == "escala_lineal":
                return self._fill_rating(container, page, str(valor), runtime_config=runtime_config)

            elif tipo in ("likert", "matriz", "matriz_checkbox"):
                return fs.fill_matrix(container, page, valor,
                                      row_selector='[class*="likert-row"], [class*="matrix-row"], '
                                                    'tr:has(input[type="radio"]), tr:has([role="radio"]), '
                                                    '[role="radiogroup"]',
                                      use_js_click=True,
                                      runtime_config=runtime_config)

            elif tipo == "nps":
                return self._fill_nps(container, page, str(valor), runtime_config=runtime_config)

            elif tipo == "desplegable":
                return fs.fill_dropdown(container, page, str(valor), runtime_config=runtime_config)

            elif tipo == "fecha":
                return fs.fill_date(container, str(valor), runtime_config=runtime_config)

            elif tipo == "hora":
                return fs.fill_time(container, str(valor), runtime_config=runtime_config)

            elif tipo == "ranking":
                return self._fill_ranking(container, page, valor, runtime_config=runtime_config)

            else:
                return fs.auto_detect_and_fill(container, page, valor, use_js_click=True, runtime_config=runtime_config)

        except Exception as e:
            print(f"    [MS] Error {tipo}: {e}")
            return False

    # ========== MS-SPECIFIC: RATING ==========

    def _fill_rating(self, container, page, valor: str, runtime_config: dict | None = None) -> bool:
        """Llena escala de calificación (estrellas, números)."""
        # Intentar como radio con JS click (MS Forms necesita esto)
        if fs.click_option_by_text(
            container, page, valor, "radio", use_js_click=True, runtime_config=runtime_config
        ):
            return True

        # Botones de rating específicos de MS Forms
        rating_buttons = container.locator(
            '[class*="rating"] button, [class*="star"], '
            '[class*="scale"] button, button[aria-label*="star"], '
            'button[aria-posinset]'
        )
        count = rating_buttons.count()
        if count > 0 and valor.isdigit():
            idx = int(valor) - 1
            if 0 <= idx < count:
                try:
                    rating_buttons.nth(idx).click()
                    pause_action(runtime_config, multiplier=0.8)
                    return True
                except Exception:
                    pass

        return False

    # ========== MS-SPECIFIC: NPS ==========

    def _fill_nps(self, container, page, valor: str, runtime_config: dict | None = None) -> bool:
        """Llena NPS (0-10)."""
        if fs.click_option_by_text(
            container, page, valor, "radio", use_js_click=True, runtime_config=runtime_config
        ):
            return True

        nps_buttons = container.locator(
            'button[aria-label*="0"], button[aria-label*="1"], '
            '[class*="nps"] button, [class*="score"] button'
        )
        if nps_buttons.count() >= 10:
            try:
                idx = int(valor)
                if 0 <= idx <= 10 and idx < nps_buttons.count():
                    nps_buttons.nth(idx).click()
                    pause_action(runtime_config, multiplier=0.8)
                    return True
            except (ValueError, Exception):
                pass

        return self._fill_rating(container, page, valor, runtime_config=runtime_config)

    # ========== MS-SPECIFIC: RANKING ==========

    def _fill_ranking(self, container, page, valor, runtime_config: dict | None = None) -> bool:
        """Ranking con botones up/down o drag&drop."""
        if isinstance(valor, str):
            return fs.click_option_by_text(
                container, page, valor, "radio", use_js_click=True, runtime_config=runtime_config
            )

        if isinstance(valor, list):
            return fs.fill_ranking(container, page, valor, runtime_config=runtime_config)

        return False

    # ========== MS-SPECIFIC: SUBMIT ==========

    def _click_submit_button(self, page, url: str = "", runtime_config: dict | None = None) -> bool:
        """Click en botón Enviar de MS Forms y verificar envío real."""
        # Selectores ordenados de más específico a más genérico
        submit_selectors = [
            'button[data-automation-id="submitButton"]',
            'button:has-text("Submit")',
            'button:has-text("Enviar")',
            'button:has-text("Send")',
            '#form-main-content1 button[type="submit"]',
            'input[type="submit"]',
        ]

        clicked = False
        before_state = capture_page_state(page, url)
        for sel in submit_selectors:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=1500):
                    # Scroll al botón para asegurar visibilidad
                    btn.scroll_into_view_if_needed()
                    pause_action(runtime_config, multiplier=0.8)
                    btn.click()
                    print(f"    Botón 'Enviar' clickeado ({sel[:40]})")
                    clicked = True
                    break
            except Exception:
                continue

        # JavaScript fallback - solo busca botones con texto exacto de envío
        if not clicked:
            try:
                clicked = page.evaluate("""
                    () => {
                        const btns = document.querySelectorAll('button');
                        for (const btn of btns) {
                            const text = btn.innerText.toLowerCase().trim();
                            if (['enviar', 'submit', 'send'].includes(text)) {
                                btn.click();
                                return true;
                            }
                        }
                        return false;
                    }
                """)
                if clicked:
                    print("    Botón 'Enviar' clickeado (js)")
            except Exception:
                pass

        if not clicked:
            print("    No se encontró botón de enviar")
            return False

        wait_for_post_action(page, before_state, url, runtime_config, after_submit=True)
        enviado = wait_for_submission_signal(page, url, runtime_config, submit_clicked=True)
        if enviado:
            print("    Confirmación de envío detectada")
        else:
            print("    No se confirmó el envío dentro de la ventana rápida")
        return enviado
