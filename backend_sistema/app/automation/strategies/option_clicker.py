"""
Click en opciones radio/checkbox de cualquier plataforma.
Para agregar una nueva estrategia de matching: añadir bloque en click_option_by_text.
"""
import logging

from app.automation.timing import pause_action
from app.utils.text_normalizer import normalize_for_matching as _norm_text

logger = logging.getLogger(__name__)


class OptionClicker:
    """Hace clic en radio/checkbox buscando la opción correcta con múltiples estrategias."""

    @staticmethod
    def click_option_by_text(container, page, valor: str, role: str = "radio",
                             use_js_click: bool = False, runtime_config: dict | None = None) -> bool:
        input_sel = f'input[type="{role}"]' if role in ("radio", "checkbox") else f'[role="{role}"]'
        inputs = container.locator(f'{input_sel}, [role="{role}"]')
        count = inputs.count()
        if count == 0:
            return False

        option_texts = OptionClicker._get_option_texts(container, count, role)
        valor_norm = _norm_text(valor)

        # Estrategia 0: match por atributo value
        for idx in range(count):
            try:
                val_attr = inputs.nth(idx).get_attribute("value") or ""
                if val_attr and _norm_text(val_attr) == valor_norm:
                    return OptionClicker._click_at_index_fallback(inputs, page, idx, use_js_click, runtime_config=runtime_config)
            except Exception:
                continue

        # Estrategia 0b: aria-labelledby
        for idx in range(count):
            try:
                labelled_by = inputs.nth(idx).get_attribute("aria-labelledby") or ""
                if not labelled_by:
                    continue
                for ref_id in labelled_by.split():
                    try:
                        txt = page.locator(f'#{ref_id}').first.inner_text(timeout=300).strip()
                        if txt and _norm_text(txt) == valor_norm:
                            return OptionClicker._click_at_index_fallback(inputs, page, idx, use_js_click, runtime_config=runtime_config)
                    except Exception:
                        continue
            except Exception:
                continue

        # Estrategia 1: match exacto normalizado
        for idx, text in enumerate(option_texts):
            if _norm_text(text) == valor_norm:
                return OptionClicker._click_at_index_fallback(inputs, page, idx, use_js_click, runtime_config=runtime_config)

        # Estrategia 2: match parcial
        for idx, text in enumerate(option_texts):
            text_norm = _norm_text(text)
            if valor_norm and text_norm and (valor_norm in text_norm or text_norm in valor_norm):
                return OptionClicker._click_at_index_fallback(inputs, page, idx, use_js_click, runtime_config=runtime_config)

        # Estrategia 3: aria-label del input
        for idx in range(count):
            try:
                aria_norm = _norm_text(inputs.nth(idx).get_attribute("aria-label") or "")
                if aria_norm and (aria_norm == valor_norm or valor_norm in aria_norm or aria_norm in valor_norm):
                    return OptionClicker._click_at_index_fallback(inputs, page, idx, use_js_click, runtime_config=runtime_config)
            except Exception:
                continue

        # Estrategia 4: click sobre label/span con texto exacto
        try:
            scan = container.locator('label, span, div[role="checkbox"], div[role="radio"]')
            for i in range(min(scan.count(), 150)):
                try:
                    el = scan.nth(i)
                    txt = el.inner_text(timeout=250).strip()
                    if not txt or len(txt) > 120:
                        continue
                    if _norm_text(txt) == valor_norm:
                        try:
                            el.scroll_into_view_if_needed(timeout=500)
                        except Exception:
                            pass
                        try:
                            el.click(timeout=1500)
                            pause_action(runtime_config, multiplier=0.9)
                            return True
                        except Exception:
                            try:
                                page.evaluate("el => el.click()", el.element_handle())
                                pause_action(runtime_config, multiplier=0.9)
                                return True
                            except Exception:
                                continue
                except Exception:
                    continue
        except Exception:
            pass

        # Estrategia 5: índice numérico 1-based
        if valor.strip().isdigit():
            idx = int(valor.strip()) - 1
            if 0 <= idx < count:
                return OptionClicker._click_at_index(inputs, page, idx, use_js_click, runtime_config=runtime_config)

        logger.debug("No match '%s' entre: %s", valor, option_texts)
        return False

    @staticmethod
    def click_multiple_options(container, page, valores: list, role: str = "checkbox",
                               use_js_click: bool = False, runtime_config: dict | None = None) -> bool:
        if isinstance(valores, str):
            valores = [valores]
        any_filled = False
        for val in valores:
            if OptionClicker.click_option_by_text(container, page, val, role, use_js_click, runtime_config=runtime_config):
                any_filled = True
                pause_action(runtime_config, multiplier=0.7)
        return any_filled

    # ── privados ──────────────────────────────────────────────────────────────

    @staticmethod
    def _click_at_index_fallback(inputs, page, idx: int, use_js_click: bool = False,
                                  runtime_config: dict | None = None) -> bool:
        try:
            el = inputs.nth(idx)
            targets = [
                el,
                el.locator('xpath=ancestor::label[1]').first,
                el.locator('xpath=ancestor::*[@data-automation-id="choiceItem"][1]').first,
                el.locator('xpath=ancestor::*[@role="checkbox" or @role="radio"][1]').first,
            ]
            for target in targets:
                if not OptionClicker._click_locator(target, page, use_js_click, runtime_config=runtime_config):
                    continue
                if OptionClicker._requires_selected_validation(el):
                    if OptionClicker._is_control_selected(el):
                        return True
                    continue
                return True
            if OptionClicker._requires_selected_validation(el):
                return OptionClicker._is_control_selected(el)
            return False
        except Exception:
            return False

    @staticmethod
    def _click_locator(target, page, use_js_click: bool = False, runtime_config: dict | None = None) -> bool:
        actions = []
        if use_js_click:
            actions.append(
                lambda: page.evaluate('''el => {
                    el.scrollIntoView({block: "center", inline: "nearest"});
                    if (typeof el.focus === "function") el.focus();
                    el.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
                    el.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
                    el.click();
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                    el.dispatchEvent(new Event('input', {bubbles: true}));
                }''', target.element_handle())
            )
        actions.extend([lambda: target.click(), lambda: target.click(force=True)])
        for action in actions:
            try:
                target.scroll_into_view_if_needed()
            except Exception:
                pass
            try:
                action()
                pause_action(runtime_config, multiplier=0.9)
                return True
            except Exception:
                continue
        return False

    @staticmethod
    def _click_at_index(inputs, page, idx: int, use_js_click: bool = False,
                         runtime_config: dict | None = None) -> bool:
        return OptionClicker._click_at_index_fallback(inputs, page, idx, use_js_click, runtime_config=runtime_config)

    @staticmethod
    def _get_option_texts(container, expected_count: int, role: str = "radio") -> list[str]:
        texts = []
        option_containers = container.locator(
            f'label:has(input[type="{role}"]), label:has([role="{role}"]), '
            '[class*="choice-item"], [class*="option-item"]'
        )
        count = option_containers.count()
        if count >= expected_count:
            for i in range(count):
                try:
                    text = option_containers.nth(i).inner_text(timeout=500).strip()
                    if text:
                        texts.append(text)
                except Exception:
                    texts.append("")

        if len(texts) < expected_count:
            texts = []
            inputs = container.locator(f'input[type="{role}"], [role="{role}"]')
            for i in range(min(inputs.count(), expected_count)):
                try:
                    label = inputs.nth(i).get_attribute("aria-label") or ""
                    if label.strip():
                        texts.append(label.strip())
                except Exception:
                    pass

        if len(texts) < expected_count:
            texts = []
            spans = container.locator('span')
            for i in range(spans.count()):
                try:
                    text = spans.nth(i).inner_text(timeout=300).strip()
                    if text and len(text) < 150 and not any(
                        x in text.lower() for x in ['obligatoria', 'required', '*']
                    ):
                        texts.append(text)
                except Exception:
                    continue

        return texts[:expected_count] if texts else [f"option_{i+1}" for i in range(expected_count)]

    @staticmethod
    def _requires_selected_validation(locator) -> bool:
        try:
            input_type = (locator.get_attribute("type") or "").lower()
            role = (locator.get_attribute("role") or "").lower()
            return input_type in ("radio", "checkbox") or role in ("radio", "checkbox")
        except Exception:
            return False

    @staticmethod
    def _is_control_selected(locator) -> bool:
        try:
            if (locator.get_attribute("aria-checked") or "").lower() == "true":
                return True
            return bool(locator.evaluate("el => Boolean(el.checked)"))
        except Exception:
            return False
