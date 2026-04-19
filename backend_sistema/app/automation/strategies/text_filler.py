"""
Escritura de texto en campos de formularios (input, textarea, contenteditable).
Para agregar soporte a un nuevo tipo de campo de texto: agregar selector en fill_text o método aquí.
"""
from app.automation.timing import pause_action


class TextFiller:
    """Llena campos de texto y verifica persistencia del valor."""

    @staticmethod
    def fill_text(container, valor: str, selectors: list[str] | None = None,
                  runtime_config: dict | None = None) -> bool:
        if selectors is None:
            selectors = [
                'input[type="text"]',
                'input[type="number"]',
                'input:not([type="radio"]):not([type="checkbox"]):not([type="hidden"])',
            ]
        for sel in selectors:
            try:
                el = container.locator(sel).first
                if el.is_visible(timeout=1500):
                    el.click()
                    pause_action(runtime_config, multiplier=0.8)
                    if TextFiller._fill_text_like_field(el, str(valor)):
                        return True
            except Exception:
                continue
        return False

    @staticmethod
    def fill_textarea(container, valor: str, selectors: list[str] | None = None,
                      runtime_config: dict | None = None) -> bool:
        if selectors is None:
            selectors = ['textarea', '[contenteditable="true"]']
        for sel in selectors:
            try:
                el = container.locator(sel).first
                if el.is_visible(timeout=1500):
                    el.click()
                    pause_action(runtime_config, multiplier=0.8)
                    if TextFiller._fill_text_like_field(el, str(valor)):
                        return True
            except Exception:
                continue
        return TextFiller.fill_text(container, valor, runtime_config=runtime_config)

    @staticmethod
    def _fill_text_like_field(locator, valor: str) -> bool:
        expected = str(valor)
        for action in (
            lambda: TextFiller._fill_with_playwright(locator, expected),
            lambda: TextFiller._fill_with_js(locator, expected),
        ):
            try:
                action()
                final_value = TextFiller._read_field_value(locator)
                if TextFiller._field_value_matches(final_value, expected):
                    return True
            except Exception:
                continue
        return False

    @staticmethod
    def _fill_with_playwright(locator, valor: str) -> None:
        locator.fill("")
        locator.fill(valor)
        locator.dispatch_event("input")
        locator.dispatch_event("change")

    @staticmethod
    def _fill_with_js(locator, valor: str) -> None:
        locator.evaluate(
            """(el, value) => {
                const text = String(value ?? "");
                el.focus();
                if (el.isContentEditable) {
                    el.textContent = "";
                    el.dispatchEvent(new InputEvent("input", {bubbles: true, data: ""}));
                    el.textContent = text;
                } else {
                    el.value = "";
                    el.dispatchEvent(new InputEvent("input", {bubbles: true, data: ""}));
                    el.value = text;
                }
                el.dispatchEvent(new Event("input", {bubbles: true}));
                el.dispatchEvent(new Event("change", {bubbles: true}));
                el.dispatchEvent(new Event("blur", {bubbles: true}));
            }""",
            valor,
        )

    @staticmethod
    def _read_field_value(locator) -> str:
        try:
            value = locator.evaluate(
                """el => {
                    if (el.isContentEditable) return (el.textContent || "").trim();
                    if ("value" in el) return (el.value || "").toString().trim();
                    return (el.textContent || "").trim();
                }"""
            )
            return str(value or "").strip()
        except Exception:
            return ""

    @staticmethod
    def _field_value_matches(actual: str, expected: str) -> bool:
        actual, expected = str(actual or "").strip(), str(expected or "").strip()
        if actual == expected:
            return True
        if actual.replace(" ", "") == expected.replace(" ", ""):
            return True
        actual_digits = "".join(ch for ch in actual if ch.isdigit())
        expected_digits = "".join(ch for ch in expected if ch.isdigit())
        return bool(actual_digits and expected_digits and actual_digits == expected_digits)
