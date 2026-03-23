"""
Llenador específico para Microsoft Forms.
Usa FillingStrategies compartidas + selectores específicos de MS Forms.
"""
import time

from app.automation.filling_strategies import FillingStrategies
from app.constants.question_types import TIPOS_NO_LLENABLES

# Selectores específicos de MS Forms
MS_TEXT_SELECTORS = [
    'input[aria-label="Single line text"]',
    'input[type="text"]',
    'input:not([type="radio"]):not([type="checkbox"]):not([type="hidden"])',
]
MS_TEXTAREA_SELECTORS = [
    'textarea',
    'input[aria-label="Long answer text"]',
    '[contenteditable="true"]',
]
MS_NUMBER_SELECTORS = [
    'input[type="number"]',
    'input[inputmode="numeric"]',
    'input[aria-label*="number" i]',
    'input[aria-label*="número" i]',
    'input[type="text"]',
    'input:not([type="radio"]):not([type="checkbox"]):not([type="hidden"])',
]

fs = FillingStrategies()


class MSFormsFiller:
    """Llena formularios de Microsoft Forms usando selectores nativos."""

    def fill_page(self, page, respuestas: list):
        """Llena todas las respuestas de una página de MS Forms."""
        try:
            page.wait_for_selector('#question-list', timeout=10000)
        except Exception:
            print("    [MS] No se encontró #question-list")
            return

        time.sleep(1)

        for resp_idx, resp in enumerate(respuestas):
            tipo = resp["tipo"]
            valor = resp["valor"]
            pregunta = resp["pregunta"]

            container = self._find_question(page, resp_idx, pregunta)
            if not container:
                print(f"    [MS] No encontré: {pregunta[:50]}")
                continue

            filled = self._fill_element(container, page, tipo, valor, pregunta)

            if filled:
                print(f"    OK: {pregunta[:50]}")
            else:
                print(f"    FALLÓ: {pregunta[:50]}")

            time.sleep(0.4)

    def click_submit(self, page) -> bool:
        """Click en botón Enviar/Submit de MS Forms."""
        return self._click_submit_button(page)

    def click_next(self, page) -> bool:
        """Click en botón Siguiente/Next de MS Forms."""
        for sel in ['button:has-text("Siguiente")', 'button:has-text("Next")', 'button[data-automation-id="nextButton"]']:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=2000):
                    btn.click()
                    time.sleep(1.5)
                    return True
            except Exception:
                continue
        return False

    # ========== ENCONTRAR PREGUNTA ==========

    def _find_question(self, page, expected_idx: int, pregunta: str):
        """Encuentra la div de la pregunta en #question-list."""
        question_divs = page.locator('#question-list > div')
        total = question_divs.count()
        if total == 0:
            return None

        visible_divs = []
        for i in range(total):
            div = question_divs.nth(i)
            try:
                if div.is_visible(timeout=500):
                    visible_divs.append(div)
            except Exception:
                continue

        # Buscar por texto
        preg_lower = pregunta.lower().strip()[:35]
        for div in visible_divs:
            try:
                text = div.inner_text(timeout=2000).lower().strip()
                if preg_lower in text:
                    return div
            except Exception:
                continue

        # Fallback: por índice
        if expected_idx < len(visible_divs):
            return visible_divs[expected_idx]

        return None

    # ========== ROUTER DE TIPOS ==========

    def _fill_element(self, container, page, tipo: str, valor, pregunta: str) -> bool:
        """Redirige al método correcto según el tipo de pregunta."""
        try:
            if tipo in TIPOS_NO_LLENABLES:
                print(f"    [MS] SKIP ({tipo}): {pregunta[:40]}")
                return True

            if tipo == "texto":
                return fs.fill_text(container, valor, MS_TEXT_SELECTORS)

            elif tipo == "numero":
                return fs.fill_text(container, valor, MS_NUMBER_SELECTORS)

            elif tipo == "parrafo":
                return fs.fill_textarea(container, valor, MS_TEXTAREA_SELECTORS)

            elif tipo == "opcion_multiple":
                return fs.click_option_by_text(container, page, str(valor), "radio", use_js_click=True)

            elif tipo == "seleccion_multiple":
                return fs.click_multiple_options(container, page, valor, "checkbox", use_js_click=True)

            elif tipo == "escala_lineal":
                return self._fill_rating(container, page, str(valor))

            elif tipo in ("likert", "matriz", "matriz_checkbox"):
                return fs.fill_matrix(container, page, valor,
                                      row_selector='[class*="likert-row"], [class*="matrix-row"], '
                                                    'tr:has(input[type="radio"]), tr:has([role="radio"]), '
                                                    '[role="radiogroup"]',
                                      use_js_click=True)

            elif tipo == "nps":
                return self._fill_nps(container, page, str(valor))

            elif tipo == "desplegable":
                return fs.fill_dropdown(container, page, str(valor))

            elif tipo == "fecha":
                return fs.fill_date(container, str(valor))

            elif tipo == "hora":
                return fs.fill_time(container, str(valor))

            elif tipo == "ranking":
                return self._fill_ranking(container, page, valor)

            else:
                return fs.auto_detect_and_fill(container, page, valor, use_js_click=True)

        except Exception as e:
            print(f"    [MS] Error {tipo}: {e}")
            return False

    # ========== MS-SPECIFIC: RATING ==========

    def _fill_rating(self, container, page, valor: str) -> bool:
        """Llena escala de calificación (estrellas, números)."""
        # Intentar como radio con JS click (MS Forms necesita esto)
        if fs.click_option_by_text(container, page, valor, "radio", use_js_click=True):
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
                    time.sleep(0.3)
                    return True
                except Exception:
                    pass

        return False

    # ========== MS-SPECIFIC: NPS ==========

    def _fill_nps(self, container, page, valor: str) -> bool:
        """Llena NPS (0-10)."""
        if fs.click_option_by_text(container, page, valor, "radio", use_js_click=True):
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
                    time.sleep(0.3)
                    return True
            except (ValueError, Exception):
                pass

        return self._fill_rating(container, page, valor)

    # ========== MS-SPECIFIC: RANKING ==========

    def _fill_ranking(self, container, page, valor) -> bool:
        """Ranking con botones up/down o drag&drop."""
        if isinstance(valor, str):
            return fs.click_option_by_text(container, page, valor, "radio", use_js_click=True)

        if isinstance(valor, list):
            return fs.fill_ranking(container, page, valor)

        return False

    # ========== MS-SPECIFIC: SUBMIT ==========

    def _click_submit_button(self, page) -> bool:
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
        for sel in submit_selectors:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=1500):
                    # Scroll al botón para asegurar visibilidad
                    btn.scroll_into_view_if_needed()
                    time.sleep(0.3)
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

        # Esperar a que MS Forms procese el envío
        return self._wait_for_submission(page)

    def _wait_for_submission(self, page) -> bool:
        """Espera y verifica que MS Forms realmente procesó el envío."""
        # Esperar hasta 15 segundos por la confirmación real
        for _ in range(15):
            time.sleep(1)
            try:
                contenido = page.content().lower()

                # Textos de confirmación reales de MS Forms
                confirmation_texts = [
                    "your response was submitted",
                    "thanks!",
                    "thank you",
                    "gracias",
                    "tu respuesta se envió",
                    "se envió tu respuesta",
                    "your response has been submitted",
                    "response was submitted",
                ]
                for texto in confirmation_texts:
                    if texto in contenido:
                        print("    Confirmación de envío detectada")
                        return True

                # Detectar página de confirmación de MS Forms (class típica)
                confirmation_page = page.locator(
                    '[class*="thank"], [class*="confirmation"], '
                    '[data-automation-id="thankYouMessage"], '
                    '[class*="post-submit"]'
                )
                if confirmation_page.count() > 0:
                    print("    Página de confirmación detectada")
                    return True

            except Exception:
                continue

        print("    No se confirmó el envío después de 15s")
        return False
