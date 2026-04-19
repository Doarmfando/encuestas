"""
Utilidades de formularios: detectar y localizar preguntas, auto-detectar tipo de campo.
Para agregar soporte a un nuevo tipo de campo en auto_detect: añadir bloque aquí.
"""
from app.automation.strategies.text_filler import TextFiller
from app.automation.strategies.option_clicker import OptionClicker
from app.automation.strategies.special_fields import SpecialFieldFiller


class FormUtils:
    """Localiza preguntas y auto-detecta tipos de campos."""

    @staticmethod
    def find_question_container(page, pregunta: str, container_selectors: list[str] | None = None):
        if container_selectors is None:
            container_selectors = ['[class*="question"]', '.form-group', 'fieldset', '[role="group"]']

        for sel in container_selectors:
            try:
                for c in page.locator(sel).all():
                    try:
                        text = c.inner_text(timeout=2000)
                        if pregunta.lower().strip()[:35] in text.lower().strip():
                            return c
                    except Exception:
                        continue
            except Exception:
                continue

        try:
            text_el = page.locator(f'text="{pregunta[:50]}"').first
            if text_el.is_visible(timeout=2000):
                parent = text_el
                for _ in range(4):
                    parent = parent.locator('..')
                    if parent.locator('input, textarea, [role="radio"], [role="checkbox"]').count() > 0:
                        return parent
        except Exception:
            pass
        return None

    @staticmethod
    def auto_detect_and_fill(container, page, valor, use_js_click: bool = False,
                              runtime_config: dict | None = None) -> bool:
        valor_str = str(valor) if not isinstance(valor, list) else str(valor[0])

        if container.locator('input[type="radio"], [role="radio"]').count() > 0:
            return OptionClicker.click_option_by_text(container, page, valor_str, "radio", use_js_click, runtime_config=runtime_config)
        if container.locator('input[type="checkbox"], [role="checkbox"]').count() > 0:
            vals = valor if isinstance(valor, list) else [valor_str]
            return OptionClicker.click_multiple_options(container, page, vals, "checkbox", use_js_click, runtime_config=runtime_config)
        if container.locator('textarea').count() > 0:
            return TextFiller.fill_textarea(container, valor_str, runtime_config=runtime_config)
        if container.locator('select, [role="combobox"]').count() > 0:
            return SpecialFieldFiller.fill_dropdown(container, page, valor_str, runtime_config=runtime_config)
        if container.locator('input:not([type="hidden"])').count() > 0:
            return TextFiller.fill_text(container, valor_str, runtime_config=runtime_config)
        return False
