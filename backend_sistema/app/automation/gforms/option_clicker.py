"""
Click en opciones radio/checkbox de Google Forms.
Solo responsabilidad: hacer clic en la opción correcta y verificar la selección.
Para agregar un nuevo fallback de click: agregar un lambda en _click_control o _click_text_node.
"""
from app.automation.gforms._base import (
    normalize_match_text, prepare_scope, is_control_selected,
    score_option_candidate, click_control,
)
from app.automation.gforms.question_finder import QuestionFinder
from app.automation.timing import pause_action


class OptionClicker:
    """Hace clic en radio/checkbox validando que quede marcado."""

    def __init__(self):
        self._finder = QuestionFinder()

    def click(
        self, page, texto_opcion: str, role: str = "radio",
        container=None, pregunta: str = "", runtime_config: dict | None = None,
    ) -> bool:
        target = normalize_match_text(texto_opcion)
        if not target:
            return False

        scopes = [container or page]
        allow_refind = not (runtime_config and runtime_config.get("speed_profile") in ("turbo", "turbo_plus"))
        if pregunta and allow_refind:
            try:
                fresh = page.locator('[role="listitem"]').all()
                refound = self._finder.find(page, pregunta, fresh, runtime_config)
                if refound and refound != container:
                    scopes.append(refound)
            except Exception:
                pass

        tried: set = set()
        for scope in scopes:
            if id(scope) in tried:
                continue
            tried.add(id(scope))
            if self._click_in_scope(scope, target, role, runtime_config):
                return True

        if self._click_unique_on_page(page, target, role, runtime_config):
            return True

        print(f"      No encontré {role}: '{str(texto_opcion).strip()[:40]}'")
        return False

    def click_otro(
        self, page, valor: str, role: str, container=None,
        pregunta: str = "", runtime_config: dict | None = None,
    ) -> bool:
        scope = container or page
        prepare_scope(scope)
        try:
            if role == "radio":
                otro = scope.locator('[data-value="__other_option__"], [aria-label="Otro"], [aria-label="Other"]').first
            else:
                otro = scope.locator('[role="checkbox"][aria-label="Otro"], [role="checkbox"][aria-label="Other"]').first

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
        return self.click(page, "Otro", role, container, pregunta=pregunta, runtime_config=runtime_config)

    # ── privados ──────────────────────────────────────────────────────────────

    def _click_in_scope(self, scope, target: str, role: str, runtime_config) -> bool:
        prepare_scope(scope)
        for _, control in self._matching_controls(scope, target, role):
            if click_control(control, runtime_config):
                return True
        for _, node in self._matching_text_nodes(scope, target):
            if self._click_text_node(scope, node, target, role, runtime_config):
                return True
        return False

    def _click_unique_on_page(self, page, target: str, role: str, runtime_config) -> bool:
        matches = self._matching_controls(page, target, role)
        return len(matches) == 1 and click_control(matches[0][1], runtime_config)

    def _matching_controls(self, scope, target: str, role: str) -> list:
        matches = []
        try:
            controls = scope.locator(f'[role="{role}"], input[type="{role}"]').all()
        except Exception:
            return matches
        for control in controls:
            try:
                s = score_option_candidate(self._collect_labels(control), target)
                if s > 0:
                    matches.append((s, control))
            except Exception:
                continue
        matches.sort(key=lambda x: x[0], reverse=True)
        return matches

    def _matching_text_nodes(self, scope, target: str) -> list:
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
            s = score_option_candidate([text], target)
            if s > 0:
                matches.append((s, node))
        matches.sort(key=lambda x: x[0], reverse=True)
        return matches[:8]

    def _click_text_node(self, scope, node, target: str, role: str, runtime_config) -> bool:
        try:
            candidate = node.locator(
                f'xpath=ancestor-or-self::*[@role="{role}" or (self::input and @type="{role}")][1]'
            )
            if candidate.count() > 0 and click_control(candidate.first, runtime_config):
                return True
        except Exception:
            pass
        for click_action in (
            lambda: node.click(),
            lambda: node.click(force=True),
            lambda: node.evaluate(
                """el => {
                    const t = el.closest('[role="radio"], [role="checkbox"], label, div, span') || el;
                    t.scrollIntoView({block: "center", inline: "nearest"});
                    t.click();
                }"""
            ),
        ):
            try:
                click_action()
                pause_action(runtime_config, multiplier=0.7)
                if self._scope_has_selected(scope, target, role):
                    return True
            except Exception:
                continue
        return False

    def _scope_has_selected(self, scope, target: str, role: str) -> bool:
        try:
            selected = scope.locator(
                f'[role="{role}"][aria-checked="true"], input[type="{role}"]:checked'
            ).all()
        except Exception:
            return False
        for control in selected:
            try:
                if score_option_candidate(self._collect_labels(control), target) >= 1000:
                    return True
            except Exception:
                continue
        return False

    @staticmethod
    def _collect_labels(control) -> list[str]:
        try:
            texts = control.evaluate(
                """el => {
                    const out = [];
                    const add = v => { const t = (v||'').toString().trim(); if (t && !out.includes(t)) out.push(t); };
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
