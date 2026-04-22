"""
Manejo de dropdowns personalizados de Google Forms (role=listbox).
Solo responsabilidad: abrir el dropdown y seleccionar la opción correcta.
Para agregar soporte a un nuevo tipo de dropdown (ej. combobox nativo): agregar método aquí.
"""
import logging
from app.automation.gforms._base import normalize_match_text, prepare_scope, score_option_candidate
from app.automation.timing import pause_action

logger = logging.getLogger(__name__)


class DropdownHandler:
    """Abre y selecciona opciones en dropdowns de Google Forms."""

    def select(self, page, pregunta: str, valor: str, container=None, runtime_config: dict | None = None) -> bool:
        scope = container or page
        prepare_scope(scope)
        target = normalize_match_text(valor)

        dropdowns = self._collect_dropdowns(page, scope, container, pregunta)
        tried: set = set()
        for lb in dropdowns:
            if id(lb) in tried:
                continue
            tried.add(id(lb))
            try:
                if not lb.is_visible(timeout=500):
                    continue
            except Exception:
                continue

            if self._has_value(page, lb, target):
                return True
            if not self._open(page, lb):
                continue

            pause_action(runtime_config, multiplier=1.0)
            if self._click_option(page, lb, target, runtime_config):
                pause_action(runtime_config, multiplier=0.8)
                if self._has_value(page, lb, target):
                    return True
                if container:
                    try:
                        for refreshed in container.locator('[role="listbox"]').all():
                            if self._has_value(page, refreshed, target):
                                return True
                    except Exception:
                        pass
            try:
                page.keyboard.press("Escape")
                pause_action(runtime_config, multiplier=0.6)
            except Exception:
                logger.debug("No se pudo enviar Escape para cerrar dropdown")
        return False

    # ── privados ──────────────────────────────────────────────────────────────

    def _collect_dropdowns(self, page, scope, container, pregunta: str) -> list:
        dropdowns = []
        try:
            dropdowns.extend(scope.locator('[role="listbox"]').all())
        except Exception:
            pass
        if container and not dropdowns:
            try:
                lb = page.locator(f'[role="listbox"]:near(:text("{pregunta[:40]}"))').first
                if lb and lb.is_visible(timeout=400):
                    dropdowns.append(lb)
            except Exception:
                pass
        return dropdowns

    def _open(self, page, listbox) -> bool:
        for action in (
            lambda: listbox.click(),
            lambda: listbox.click(force=True),
            lambda: listbox.evaluate("""el => { el.scrollIntoView({block: "center", inline: "nearest"}); el.click(); }"""),
        ):
            try:
                listbox.scroll_into_view_if_needed()
            except Exception:
                pass
            try:
                action()
                expanded = (listbox.get_attribute("aria-expanded") or "").lower()
                if expanded == "true" or self._visible_options(page):
                    return True
            except Exception:
                continue
        return False

    def _click_option(self, page, listbox, target: str, runtime_config) -> bool:
        try:
            options = page.locator('[role="option"]').all()
        except Exception:
            return False

        matches = []
        for option in options:
            try:
                if hasattr(option, "is_visible") and not option.is_visible(timeout=200):
                    continue
                text = option.inner_text(timeout=300).strip()
            except Exception:
                continue
            s = score_option_candidate([text], target)
            if s > 0:
                matches.append((s, option))

        matches.sort(key=lambda x: x[0], reverse=True)
        for _, option in matches:
            try:
                option.scroll_into_view_if_needed()
            except Exception:
                pass
            for action, confirm_enter in (
                (lambda: option.click(), False),
                (lambda: option.click(force=True), False),
                (lambda: option.evaluate("""el => { el.scrollIntoView({block:"center",inline:"nearest"}); el.click(); }"""), False),
                (lambda: option.focus(), True),
                (lambda: option.hover(), True),
            ):
                try:
                    action()
                    if confirm_enter:
                        page.keyboard.press("Enter")
                    pause_action(runtime_config, multiplier=0.6)
                    if self._has_value(page, listbox, target):
                        return True
                except Exception:
                    continue

        if matches and self._keyboard_select(page, listbox, matches, target, runtime_config):
            return True
        return False

    def _has_value(self, page, listbox, target: str) -> bool:
        try:
            values = listbox.evaluate(
                """el => {
                    const out = [];
                    const add = v => { const t=(v||'').toString().trim(); if(t && !out.includes(t)) out.push(t); };
                    add(el.getAttribute && el.getAttribute('aria-label'));
                    add(el.getAttribute && el.getAttribute('data-value'));
                    add((el.innerText||el.textContent||'').split('\n')[0]);
                    return out.slice(0, 8);
                }"""
            )
        except Exception:
            values = []

        try:
            for option in page.locator('[role="option"][aria-selected="true"], [role="option"][aria-checked="true"]').all():
                try:
                    values.append(option.inner_text(timeout=200).strip())
                except Exception:
                    continue
        except Exception:
            pass

        placeholder_tokens = {"elige", "choose", "select"}
        for value in (values if isinstance(values, list) else []):
            norm = normalize_match_text(value)
            if not norm or norm in placeholder_tokens:
                continue
            if norm == target:
                return True
        return False

    def _keyboard_select(self, page, listbox, matches, target: str, runtime_config) -> bool:
        try:
            visible = [o for o in page.locator('[role="option"]').all()
                       if hasattr(o, "is_visible") and o.is_visible(timeout=150)]
            if not visible:
                return False
            best = matches[0][1]
            idx = next((i for i, o in enumerate(visible) if o == best), None)
            if idx is None:
                return False
            try:
                listbox.focus()
            except Exception:
                listbox.click(force=True)
            page.keyboard.press("Home")
            pause_action(runtime_config, multiplier=0.4)
            for _ in range(idx):
                page.keyboard.press("ArrowDown")
                pause_action(runtime_config, multiplier=0.25)
            page.keyboard.press("Enter")
            pause_action(runtime_config, multiplier=0.6)
            return self._has_value(page, listbox, target)
        except Exception:
            return False

    @staticmethod
    def _visible_options(page) -> int:
        try:
            return sum(
                1 for o in page.locator('[role="option"]').all()
                if hasattr(o, "is_visible") and o.is_visible(timeout=150)
            )
        except Exception:
            return 0
