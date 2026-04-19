"""
Escritura de texto en inputs de respuesta corta y párrafo de Google Forms.
Solo responsabilidad: rellenar campos de texto. Para agregar un nuevo tipo de input
(ej. contenteditable): agregar un selector en SHORT_ANSWER_INPUT_SELECTORS o un método aquí.
"""
import re
from app.automation.gforms._base import prepare_scope
from app.utils.question_inference import (
    NUMERIC_SHORT_ANSWER_INPUT_SELECTORS,
    SHORT_ANSWER_INPUT_SELECTORS,
    TEXT_SHORT_ANSWER_INPUT_SELECTORS,
    looks_numeric_question,
    collect_input_hints,
)


class TextWriter:
    """Escribe en inputs de texto y textarea de Google Forms."""

    def write(self, page, valor, container=None, pregunta: str = "", tipo: str = "texto") -> bool:
        scope = container or page
        prepare_scope(scope)
        try:
            hints = self._collect_hints(scope)
            prefer_numeric = tipo == "numero" or looks_numeric_question(pregunta, hints)
            selector_groups = [
                NUMERIC_SHORT_ANSWER_INPUT_SELECTORS if prefer_numeric else TEXT_SHORT_ANSWER_INPUT_SELECTORS,
                TEXT_SHORT_ANSWER_INPUT_SELECTORS if prefer_numeric else NUMERIC_SHORT_ANSWER_INPUT_SELECTORS,
                SHORT_ANSWER_INPUT_SELECTORS,
            ]
            usados: set = set()
            for selectors in selector_groups:
                key = tuple(selectors)
                if key in usados:
                    continue
                usados.add(key)
                if self._fill_with_selectors(scope, valor, selectors):
                    return True
            if container:
                return self.write(page, valor, None, pregunta=pregunta, tipo=tipo)
            print("      No encontré campo de respuesta corta")
            return False
        except Exception as e:
            print(f"      Error texto: {e}")
            return False

    def write_paragraph(self, page, valor, container=None) -> bool:
        scope = container or page
        prepare_scope(scope)
        try:
            for ta in scope.locator("textarea").all():
                if ta.is_visible() and not ta.input_value():
                    ta.fill(str(valor))
                    return True
            return self.write(page, valor, container, tipo="parrafo")
        except Exception:
            return False

    # ── privados ──────────────────────────────────────────────────────────────

    def _fill_with_selectors(self, scope, valor, selectors: list[str]) -> bool:
        valor_str = str(valor).strip()
        try:
            inputs = scope.locator(", ".join(selectors))
            overwrite_candidates = []
            for idx in range(inputs.count()):
                inp = inputs.nth(idx)
                try:
                    if not inp.is_visible(timeout=500) or self._is_temporal(inp):
                        continue
                    current = (inp.input_value() or "").strip()
                    if self._matches(current, valor_str):
                        return True
                    if current:
                        overwrite_candidates.append(inp)
                        continue
                    if self._try_fill(inp, valor_str):
                        return True
                except Exception:
                    continue
            for inp in overwrite_candidates:
                if self._try_fill(inp, valor_str):
                    return True
        except Exception:
            pass
        return False

    def _try_fill(self, inp, valor: str) -> bool:
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
                        el.focus(); el.value = "";
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
            final = (inp.input_value() or "").strip()
        except Exception:
            final = ""
        return self._matches(final, valor) or bool(final)

    @staticmethod
    def _matches(actual: str, expected: str) -> bool:
        actual, expected = str(actual or "").strip(), str(expected or "").strip()
        if actual == expected:
            return True
        if actual.replace(" ", "") == expected.replace(" ", ""):
            return True
        exp_d = re.sub(r"\D", "", expected)
        act_d = re.sub(r"\D", "", actual)
        return bool(exp_d and act_d and exp_d == act_d)

    @staticmethod
    def _is_temporal(locator) -> bool:
        try:
            if (locator.get_attribute("type") or "").lower() in ("date", "time"):
                return True
            attrs = " ".join([
                locator.get_attribute("aria-label") or "",
                locator.get_attribute("placeholder") or "",
            ]).lower()
            return any(t in attrs for t in ("dia", "día", "day", "mes", "month", "ano", "año", "year", "hora", "hour", "minuto", "minute"))
        except Exception:
            return False

    def _collect_hints(self, scope, max_inputs: int = 3) -> str:
        return collect_input_hints(scope, SHORT_ANSWER_INPUT_SELECTORS, max_inputs)
