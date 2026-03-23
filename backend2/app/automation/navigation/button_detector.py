"""
Deteccion de botones de navegacion con multiples estrategias.
"""
import time

from app.automation.navigation.selectors import detectar_plataforma, GENERIC
from app.automation.navigation.waits import (
    capture_page_state,
    has_success_signal,
    wait_for_post_action,
    wait_for_submission_signal,
)
from app.automation.timing import pause_action
from app.utils.question_inference import SHORT_ANSWER_INPUT_SELECTORS, dummy_value_for_question


def detectar_botones(page, url: str = "") -> list[str]:
    """Detecta botones de navegacion visibles usando la plataforma apropiada."""
    platform = detectar_plataforma(url) if url else GENERIC
    botones = []

    all_texts = (
        platform.get("next_texts", [])
        + platform.get("submit_texts", [])
        + platform.get("back_texts", [])
    )

    for nombre in all_texts:
        try:
            btn = page.locator(
                f'[role="button"]:has-text("{nombre}"), '
                f'button:has-text("{nombre}"), '
                f'span:has-text("{nombre}")'
            )
            if btn.count() > 0:
                normalized = _normalizar_boton(nombre, platform)
                if normalized and normalized not in botones:
                    botones.append(normalized)
        except Exception:
            pass

    try:
        borrar = page.locator('a:has-text("Borrar"), span:has-text("Borrar formulario")')
        if borrar.count() > 0:
            botones.append("Borrar formulario")
    except Exception:
        pass

    return botones


def _normalizar_boton(texto: str, platform: dict) -> str:
    """Normaliza el texto del boton a nombres estandar."""
    texto_lower = texto.lower()
    for t in platform.get("next_texts", []):
        if t.lower() == texto_lower:
            return "Siguiente"
    for t in platform.get("submit_texts", []):
        if t.lower() == texto_lower:
            return "Enviar"
    for t in platform.get("back_texts", []):
        if t.lower() == texto_lower:
            return "Atrás"
    return texto


def click_boton(page, nombre: str, url: str = "", runtime_config: dict | None = None) -> bool:
    """Hace click en un boton de navegacion con multiples estrategias."""
    platform = detectar_plataforma(url) if url else GENERIC
    textos_buscar = _expandir_nombre_boton(nombre, platform)
    before_state = capture_page_state(page, url)
    after_submit = nombre == "Enviar"

    try:
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            pause_action(runtime_config, multiplier=0.8)
        except Exception:
            pass

        for texto in textos_buscar:
            botones = page.locator(f'[role="button"]:has-text("{texto}")').all()
            for btn in botones:
                if btn.is_visible():
                    btn.scroll_into_view_if_needed()
                    btn.click()
                    changed = wait_for_post_action(page, before_state, url, runtime_config, after_submit=after_submit)
                    print(
                        f"    Boton '{texto}' clickeado (role-button)"
                        if changed else f"    Boton '{texto}' clickeado pero no hubo cambio de pagina (role-button)"
                    )
                    return changed

            clicked = page.evaluate(f'''() => {{
                const buttons = document.querySelectorAll('[role="button"], button, input[type="submit"]');
                for (const btn of buttons) {{
                    if (btn.textContent.trim().includes("{texto}") || btn.value === "{texto}") {{
                        btn.click();
                        return true;
                    }}
                }}
                return false;
            }}''')
            if clicked:
                changed = wait_for_post_action(page, before_state, url, runtime_config, after_submit=after_submit)
                print(
                    f"    Boton '{texto}' clickeado (js)"
                    if changed else f"    Boton '{texto}' clickeado pero no hubo cambio de pagina (js)"
                )
                return changed

            try:
                span = page.locator(f'[role="button"] span:text-is("{texto}")').first
                if span.is_visible():
                    span.click()
                    changed = wait_for_post_action(page, before_state, url, runtime_config, after_submit=after_submit)
                    print(
                        f"    Boton '{texto}' clickeado (span)"
                        if changed else f"    Boton '{texto}' clickeado pero no hubo cambio de pagina (span)"
                    )
                    return changed
            except Exception:
                pass

            try:
                btn_html = page.locator(f'button:has-text("{texto}")').first
                if btn_html.is_visible():
                    btn_html.click()
                    changed = wait_for_post_action(page, before_state, url, runtime_config, after_submit=after_submit)
                    print(
                        f"    Boton '{texto}' clickeado (button html)"
                        if changed else f"    Boton '{texto}' clickeado pero no hubo cambio de pagina (button html)"
                    )
                    return changed
            except Exception:
                pass

            try:
                submit = page.locator(f'input[type="submit"][value="{texto}"]').first
                if submit.is_visible():
                    submit.click()
                    changed = wait_for_post_action(page, before_state, url, runtime_config, after_submit=after_submit)
                    print(
                        f"    Boton '{texto}' clickeado (input submit)"
                        if changed else f"    Boton '{texto}' clickeado pero no hubo cambio de pagina (input submit)"
                    )
                    return changed
            except Exception:
                pass

            try:
                text_nodes = page.locator(f':text-is("{texto}")').all()
                for node in text_nodes:
                    try:
                        clickable = node.locator(
                            'xpath=ancestor-or-self::*[@role="button" or self::button or (self::input and @type="submit")][1]'
                        )
                        if clickable.count() == 0:
                            continue
                        btn = clickable.first
                        if btn.is_visible():
                            btn.scroll_into_view_if_needed()
                            btn.click(force=True)
                            changed = wait_for_post_action(page, before_state, url, runtime_config, after_submit=after_submit)
                            print(
                                f"    Boton '{texto}' clickeado (text-node)"
                                if changed else f"    Boton '{texto}' clickeado pero no hubo cambio de pagina (text-node)"
                            )
                            return changed
                    except Exception:
                        continue
            except Exception:
                pass

        print(f"    No encontre boton '{nombre}'")
        return False
    except Exception as e:
        print(f"    Error boton '{nombre}': {e}")
        return False


def _expandir_nombre_boton(nombre: str, platform: dict) -> list[str]:
    """Expande un nombre estandar a todos los textos posibles de la plataforma."""
    mapping = {
        "Siguiente": platform.get("next_texts", ["Siguiente", "Next"]),
        "Enviar": platform.get("submit_texts", ["Enviar", "Submit"]),
        "Atras": platform.get("back_texts", ["Atrás", "Atras", "Back"]),
        "Atrás": platform.get("back_texts", ["Atrás", "Atras", "Back"]),
    }
    return mapping.get(nombre, [nombre])


def verificar_envio(page, url: str = "", submit_clicked: bool = False, runtime_config: dict | None = None) -> bool:
    """Verifica si el formulario se envio correctamente con multiples metodos."""
    if has_success_signal(page, url, submit_clicked=submit_clicked):
        return True
    return wait_for_submission_signal(page, url, runtime_config, submit_clicked=submit_clicked)


def _hay_boton_visible(page, textos: list[str]) -> bool:
    """Chequea si alguno de los textos de navegacion sigue visible en la pagina."""
    for texto in textos:
        try:
            boton = page.locator(
                f'[role="button"]:has-text("{texto}"), button:has-text("{texto}"), input[type="submit"][value="{texto}"]'
            )
            for idx in range(boton.count()):
                try:
                    if boton.nth(idx).is_visible(timeout=200):
                        return True
                except Exception:
                    continue
        except Exception:
            continue
    return False


def llenar_dummy_pagina(page):
    """Llena campos obligatorios con valores dummy para poder avanzar."""
    try:
        items = page.locator('[role="listitem"]').all()
        for item in items:
            radios = item.locator('[role="radio"]').all()
            if radios:
                ya = item.locator('[role="radio"][aria-checked="true"]').count() > 0
                if not ya:
                    radios[0].click()
                    time.sleep(0.15)
                continue

            checks = item.locator('[role="checkbox"]').all()
            if checks:
                ya = item.locator('[role="checkbox"][aria-checked="true"]').count() > 0
                if not ya:
                    checks[0].click()
                    time.sleep(0.15)
                continue

            groups = item.locator('[role="radiogroup"]').all()
            if groups:
                for group in groups:
                    group_radios = group.locator('[role="radio"]').all()
                    ya = group.locator('[role="radio"][aria-checked="true"]').count() > 0
                    if not ya and group_radios:
                        group_radios[0].click()
                        time.sleep(0.1)
                continue

            try:
                listbox = item.locator('[role="listbox"]')
                if listbox.count() > 0:
                    listbox.first.click()
                    time.sleep(0.3)
                    options = page.locator('[role="option"]').all()
                    if len(options) > 1:
                        options[1].click()
                    time.sleep(0.2)
                    continue
            except Exception:
                pass

            for sel, value in [('input[type="date"]', "2026-01-15"), ('input[type="time"]', "12:00")]:
                for campo in item.locator(sel).all():
                    try:
                        if campo.is_visible() and not campo.input_value():
                            campo.fill(value)
                            time.sleep(0.1)
                    except Exception:
                        pass

            for sel in ['[aria-label*="Dia" i], [aria-label*="Día" i], [aria-label*="Day" i]',
                        '[aria-label*="Mes" i], [aria-label*="Month" i]',
                        '[aria-label*="Ano" i], [aria-label*="Año" i], [aria-label*="Year" i]',
                        '[aria-label*="Hora" i], [aria-label*="Hour" i]',
                        '[aria-label*="Minuto" i], [aria-label*="Minute" i]']:
                try:
                    el = item.locator(sel)
                    if el.count() > 0 and el.first.is_visible() and not el.first.input_value():
                        el.first.fill(
                            "15" if "day" in sel.lower() or "dia" in sel.lower() or "día" in sel.lower()
                            else "6" if "month" in sel.lower() or "mes" in sel.lower()
                            else "2026" if "year" in sel.lower() or "ano" in sel.lower() or "año" in sel.lower()
                            else "12" if "hour" in sel.lower() or "hora" in sel.lower()
                            else "00"
                        )
                        time.sleep(0.1)
                except Exception:
                    pass

            for campo in item.locator("textarea").all():
                try:
                    if campo.is_visible() and not campo.input_value():
                        campo.fill("respuesta")
                        time.sleep(0.1)
                except Exception:
                    pass

            question_text = ""
            try:
                question_text = item.inner_text(timeout=500)
            except Exception:
                pass

            hint_text = _collect_input_hints(item, SHORT_ANSWER_INPUT_SELECTORS)
            dummy_value = dummy_value_for_question(question_text, hint_text)
            for campo in item.locator(", ".join(SHORT_ANSWER_INPUT_SELECTORS)).all():
                try:
                    if _is_temporal_input(campo):
                        continue
                    if campo.is_visible() and not campo.input_value():
                        campo.fill(dummy_value)
                        time.sleep(0.1)
                except Exception:
                    pass
    except Exception:
        pass


def _collect_input_hints(scope, selectors: list[str], max_inputs: int = 3) -> str:
    """Junta metadatos de inputs para heuristicas de tipo."""
    hints = []
    try:
        inputs = scope.locator(", ".join(selectors))
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


def _is_temporal_input(locator) -> bool:
    """Evita tratar inputs de fecha u hora como respuesta corta comun."""
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
