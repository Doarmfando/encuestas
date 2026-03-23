"""
Estrategias compartidas de llenado de formularios.
Cada estrategia acepta selectores específicos de plataforma para máxima reutilización.

Uso:
    from app.automation.filling_strategies import FillingStrategies
    fs = FillingStrategies()
    fs.fill_text(container, "valor", selectors=["input[type='text']", "textarea"])
    fs.click_option(container, page, "opcion", role="radio")
"""
import random

from app.automation.timing import pause_action


class FillingStrategies:
    """Biblioteca de estrategias de llenado reutilizables entre plataformas."""

    # ========== TEXTO ==========

    @staticmethod
    def fill_text(container, valor: str, selectors: list[str] | None = None, runtime_config: dict | None = None) -> bool:
        """Llena un campo de texto en cualquier contenedor.

        Args:
            container: Locator de Playwright del contenedor de la pregunta.
            valor: Texto a escribir.
            selectors: Lista de selectores CSS a intentar (en orden).
        """
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
                    if FillingStrategies._fill_text_like_field(el, str(valor)):
                        return True
            except Exception:
                continue
        return False

    @staticmethod
    def fill_textarea(container, valor: str, selectors: list[str] | None = None, runtime_config: dict | None = None) -> bool:
        """Llena un campo de texto largo (textarea, contenteditable)."""
        if selectors is None:
            selectors = [
                'textarea',
                '[contenteditable="true"]',
            ]
        for sel in selectors:
            try:
                el = container.locator(sel).first
                if el.is_visible(timeout=1500):
                    el.click()
                    pause_action(runtime_config, multiplier=0.8)
                    if FillingStrategies._fill_text_like_field(el, str(valor)):
                        return True
            except Exception:
                continue
        # Fallback a input de texto
        return FillingStrategies.fill_text(container, valor, runtime_config=runtime_config)

    # ========== CLICK EN OPCIÓN (radio / checkbox) ==========

    @staticmethod
    def click_option_by_text(container, page, valor: str, role: str = "radio",
                             use_js_click: bool = False, runtime_config: dict | None = None) -> bool:
        """Hace click en un radio o checkbox buscando por texto de la opción.

        Args:
            container: Locator del contenedor de la pregunta.
            page: Playwright page (para JS click).
            valor: Texto de la opción a seleccionar.
            role: "radio" o "checkbox".
            use_js_click: Si True, usa page.evaluate('el.click()') en vez de .click().
        """
        input_sel = f'input[type="{role}"]' if role in ("radio", "checkbox") else f'[role="{role}"]'
        inputs = container.locator(f'{input_sel}, [role="{role}"]')
        count = inputs.count()

        if count == 0:
            return False

        # Obtener textos de opciones
        option_texts = FillingStrategies._get_option_texts(container, count, role)

        # Estrategia 1: match exacto
        for idx, text in enumerate(option_texts):
            if text.lower().strip() == valor.lower().strip():
                return FillingStrategies._click_at_index(inputs, page, idx, use_js_click, runtime_config=runtime_config)

        # Estrategia 2: match parcial
        for idx, text in enumerate(option_texts):
            if valor.lower().strip() in text.lower().strip() or text.lower().strip() in valor.lower().strip():
                return FillingStrategies._click_at_index(inputs, page, idx, use_js_click, runtime_config=runtime_config)

        # Estrategia 3: valor numérico como índice 1-based
        if valor.strip().isdigit():
            idx = int(valor.strip()) - 1
            if 0 <= idx < count:
                return FillingStrategies._click_at_index(inputs, page, idx, use_js_click, runtime_config=runtime_config)

        return False

    @staticmethod
    def click_multiple_options(container, page, valores: list, role: str = "checkbox",
                               use_js_click: bool = False, runtime_config: dict | None = None) -> bool:
        """Hace click en múltiples checkboxes."""
        if isinstance(valores, str):
            valores = [valores]
        any_filled = False
        for val in valores:
            if FillingStrategies.click_option_by_text(
                container, page, val, role, use_js_click, runtime_config=runtime_config
            ):
                any_filled = True
                pause_action(runtime_config, multiplier=0.7)
        return any_filled

    @staticmethod
    def _click_at_index(inputs, page, idx: int, use_js_click: bool = False, runtime_config: dict | None = None) -> bool:
        """Click en un input por índice con eventos completos."""
        try:
            el = inputs.nth(idx)
            if use_js_click:
                # Disparar eventos completos que frameworks como React necesitan
                page.evaluate('''el => {
                    el.scrollIntoView({block: "center"});
                    el.focus();
                    el.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
                    el.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
                    el.click();
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                    el.dispatchEvent(new Event('input', {bubbles: true}));
                }''', el.element_handle())
            else:
                # Click normal de Playwright (scrollea, espera actionability)
                el.scroll_into_view_if_needed()
                el.click()
            pause_action(runtime_config, multiplier=0.9)
            if FillingStrategies._requires_selected_validation(el):
                return FillingStrategies._is_control_selected(el)
            return True
        except Exception:
            return False

    @staticmethod
    def _get_option_texts(container, expected_count: int, role: str = "radio") -> list[str]:
        """Extrae textos de opciones de radio/checkbox de cualquier plataforma."""
        texts = []

        # Método 1: contenedores de opción con labels
        option_containers = container.locator(
            f'label:has(input[type="{role}"]), '
            f'label:has([role="{role}"]), '
            '[class*="choice-item"], '
            '[class*="option-item"]'
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

        # Método 2: aria-label de los inputs
        if len(texts) < expected_count:
            texts = []
            input_sel = f'input[type="{role}"], [role="{role}"]'
            inputs = container.locator(input_sel)
            for i in range(min(inputs.count(), expected_count)):
                try:
                    label = inputs.nth(i).get_attribute("aria-label") or ""
                    if label.strip():
                        texts.append(label.strip())
                except Exception:
                    pass

        # Método 3: spans sueltos (filtrados)
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

    # ========== DROPDOWN ==========

    @staticmethod
    def fill_dropdown(container, page, valor: str,
                      trigger_selectors: list[str] | None = None, runtime_config: dict | None = None) -> bool:
        """Selecciona una opción de dropdown (nativo o custom).

        Args:
            trigger_selectors: Selectores para abrir el dropdown.
        """
        # HTML select nativo
        selects = container.locator('select')
        if selects.count() > 0:
            try:
                selects.first.select_option(label=valor)
                return True
            except Exception:
                pass

        # Custom dropdown
        if trigger_selectors is None:
            trigger_selectors = [
                '[role="combobox"]',
                '[role="listbox"]',
                '[class*="dropdown"]',
                'button[class*="select"]',
            ]

        for sel in trigger_selectors:
            triggers = container.locator(sel)
            if triggers.count() > 0:
                try:
                    triggers.first.click()
                    pause_action(runtime_config, multiplier=1.0)
                    option = page.locator(
                        f'[role="option"]:has-text("{valor}"), '
                        f'[class*="dropdown-option"]:has-text("{valor}"), '
                        f'li:has-text("{valor}")'
                    ).first
                    if option.is_visible(timeout=3000):
                        option.click()
                        pause_action(runtime_config, multiplier=0.9)
                        return True
                    # Cerrar si no encontró
                    page.keyboard.press("Escape")
                    pause_action(runtime_config, multiplier=0.7)
                except Exception:
                    pass

        return False

    # ========== FECHA ==========

    @staticmethod
    def fill_date(container, valor: str,
                  day_selectors: list[str] | None = None,
                  month_selectors: list[str] | None = None,
                  year_selectors: list[str] | None = None,
                  runtime_config: dict | None = None) -> bool:
        """Llena campo de fecha con inputs separados o input[type=date]."""
        partes = FillingStrategies._parse_date(valor)
        if not partes:
            return FillingStrategies.fill_text(container, valor, runtime_config=runtime_config)
        dia, mes, anio = partes

        if day_selectors is None:
            day_selectors = [
                'input[type="date"]',
                '[aria-label*="Día" i]', '[aria-label*="Day" i]',
                'input[placeholder*="DD"]',
            ]
        if month_selectors is None:
            month_selectors = [
                '[aria-label*="Mes" i]', '[aria-label*="Month" i]',
                'input[placeholder*="MM"]',
            ]
        if year_selectors is None:
            year_selectors = [
                '[aria-label*="Año" i]', '[aria-label*="Year" i]',
                'input[placeholder*="AAAA"]', 'input[placeholder*="YYYY"]',
            ]

        # Input type=date nativo (llena todo de una vez)
        try:
            date_input = container.locator('input[type="date"]').first
            if date_input.is_visible(timeout=1000):
                date_input.fill(f"{anio:04d}-{mes:02d}-{dia:02d}")
                return True
        except Exception:
            pass

        # Inputs separados
        filled_any = False
        for sel in day_selectors:
            if 'type="date"' in sel:
                continue
            try:
                el = container.locator(sel).first
                if el.is_visible(timeout=1000):
                    el.click()
                    pause_action(runtime_config, multiplier=0.6)
                    el.fill(str(dia))
                    filled_any = True
                    break
            except Exception:
                continue

        for sel in month_selectors:
            try:
                el = container.locator(sel).first
                if el.is_visible(timeout=1000):
                    el.click()
                    pause_action(runtime_config, multiplier=0.6)
                    el.fill(str(mes))
                    filled_any = True
                    break
            except Exception:
                continue

        for sel in year_selectors:
            try:
                el = container.locator(sel).first
                if el.is_visible(timeout=1000):
                    el.click()
                    pause_action(runtime_config, multiplier=0.6)
                    el.fill(str(anio))
                    filled_any = True
                    break
            except Exception:
                continue

        return filled_any

    @staticmethod
    def _parse_date(valor: str) -> tuple | None:
        """Parsea fecha string -> (dia, mes, año)."""
        try:
            valor = str(valor).strip()
            if "-" in valor and len(valor) >= 8:
                partes = valor.split("-")
                if len(partes[0]) == 4:  # YYYY-MM-DD
                    return int(partes[2]), int(partes[1]), int(partes[0])
                return int(partes[0]), int(partes[1]), int(partes[2])
            elif "/" in valor:  # DD/MM/YYYY
                partes = valor.split("/")
                return int(partes[0]), int(partes[1]), int(partes[2])
        except Exception:
            pass
        return None

    # ========== HORA ==========

    @staticmethod
    def fill_time(container, valor: str,
                  hour_selectors: list[str] | None = None,
                  minute_selectors: list[str] | None = None,
                  runtime_config: dict | None = None) -> bool:
        """Llena campo de hora con inputs separados o input[type=time]."""
        partes = str(valor).split(":")
        hora = partes[0].strip() if len(partes) > 0 else "12"
        minuto = partes[1].strip() if len(partes) > 1 else "00"

        # Input type=time nativo
        try:
            time_input = container.locator('input[type="time"]').first
            if time_input.is_visible(timeout=1000):
                time_input.fill(f"{hora}:{minuto}")
                return True
        except Exception:
            pass

        if hour_selectors is None:
            hour_selectors = [
                '[aria-label*="Hora" i]', '[aria-label*="Hour" i]',
                'input[placeholder*="HH"]',
            ]
        if minute_selectors is None:
            minute_selectors = [
                '[aria-label*="Minuto" i]', '[aria-label*="Minute" i]',
                'input[placeholder*="MM"]',
            ]

        filled_any = False
        for sel in hour_selectors:
            try:
                el = container.locator(sel).first
                if el.is_visible(timeout=1000):
                    el.click()
                    pause_action(runtime_config, multiplier=0.6)
                    el.fill(hora)
                    filled_any = True
                    break
            except Exception:
                continue

        for sel in minute_selectors:
            try:
                el = container.locator(sel).first
                if el.is_visible(timeout=1000):
                    el.click()
                    pause_action(runtime_config, multiplier=0.6)
                    el.fill(minuto)
                    filled_any = True
                    break
            except Exception:
                continue

        if not filled_any:
            # Fallback: select dropdowns
            dropdowns = container.locator('select, [role="combobox"]')
            if dropdowns.count() >= 2:
                try:
                    dropdowns.nth(0).select_option(value=hora)
                    pause_action(runtime_config, multiplier=0.7)
                    dropdowns.nth(1).select_option(value=minuto)
                    return True
                except Exception:
                    pass

        return filled_any or FillingStrategies.fill_text(container, valor, runtime_config=runtime_config)

    # ========== LIKERT / MATRIX ==========

    @staticmethod
    def fill_matrix(container, page, valor, row_selector: str = '[role="radiogroup"]',
                    use_js_click: bool = False, runtime_config: dict | None = None) -> bool:
        """Llena pregunta tipo matriz/likert (filas x columnas).

        Args:
            valor: dict {"fila": "columna"}, list ["col1", "col2"], o str.
            row_selector: Selector para encontrar filas de la matriz.
        """
        rows = container.locator(row_selector)
        row_count = rows.count()

        if row_count == 0:
            # Intentar otros selectores de fila
            for alt_sel in ['tr:has(input[type="radio"])', '[class*="likert-row"]', '[class*="matrix-row"]']:
                rows = container.locator(alt_sel)
                row_count = rows.count()
                if row_count > 0:
                    break

        if row_count == 0:
            return False

        if isinstance(valor, dict):
            for i in range(row_count):
                row = rows.nth(i)
                try:
                    row_text = row.inner_text(timeout=2000).split("\n")[0].strip()
                except Exception:
                    row_text = ""
                for fila_key, col_val in valor.items():
                    if fila_key.lower() in row_text.lower() or row_text.lower() in fila_key.lower():
                        FillingStrategies._click_in_row(row, page, str(col_val), use_js_click, runtime_config=runtime_config)
                        pause_action(runtime_config, multiplier=0.7)
                        break

        elif isinstance(valor, list):
            for i, val in enumerate(valor):
                if i < row_count:
                    if isinstance(val, list):
                        for v in val:
                            FillingStrategies._click_in_row(
                                rows.nth(i), page, str(v), use_js_click, role="checkbox", runtime_config=runtime_config
                            )
                    else:
                        FillingStrategies._click_in_row(rows.nth(i), page, str(val), use_js_click, runtime_config=runtime_config)
                    pause_action(runtime_config, multiplier=0.7)
        else:
            # Valor único para todas las filas
            for i in range(row_count):
                FillingStrategies._click_in_row(rows.nth(i), page, str(valor), use_js_click, runtime_config=runtime_config)
                pause_action(runtime_config, multiplier=0.7)

        return True

    @staticmethod
    def _click_in_row(
        row,
        page,
        valor: str,
        use_js_click: bool = False,
        role: str = "radio",
        runtime_config: dict | None = None,
    ) -> bool:
        """Click en un radio/checkbox dentro de una fila de matriz."""
        inputs = row.locator(f'input[type="{role}"], [role="{role}"]')
        count = inputs.count()
        if count == 0:
            return False

        # Por texto de label
        labels = row.locator(f'label, td:has(input[type="{role}"]), [class*="choice"]')
        for i in range(labels.count()):
            try:
                text = labels.nth(i).inner_text(timeout=500).strip()
                if text.lower() == valor.lower() or valor.lower() in text.lower():
                    inner = labels.nth(i).locator(f'input[type="{role}"], [role="{role}"]')
                    if inner.count() > 0:
                        if use_js_click:
                            page.evaluate('el => el.click()', inner.first.element_handle())
                        else:
                            inner.first.click(force=True)
                        pause_action(runtime_config, multiplier=0.7)
                        return True
            except Exception:
                continue

        # Por índice numérico
        if valor.isdigit():
            idx = int(valor) - 1
            if 0 <= idx < count:
                try:
                    if use_js_click:
                        page.evaluate('el => el.click()', inputs.nth(idx).element_handle())
                    else:
                        inputs.nth(idx).click(force=True)
                    pause_action(runtime_config, multiplier=0.7)
                    return True
                except Exception:
                    pass

        return False

    # ========== RANKING ==========

    @staticmethod
    def fill_ranking(container, page, valor: list, runtime_config: dict | None = None) -> bool:
        """Llena ranking reordenando items con botones up/down o drag&drop."""
        ranking_items = container.locator(
            '[class*="ranking-item"], [class*="sortable-item"], '
            '[class*="drag-item"], [draggable="true"]'
        )
        item_count = ranking_items.count()

        if item_count == 0 or not isinstance(valor, list):
            return False

        # Reordenar con botones up
        for target_pos, target_text in enumerate(valor):
            for current_pos in range(item_count):
                try:
                    item = ranking_items.nth(current_pos)
                    item_text = item.inner_text(timeout=1000).strip()
                    if target_text.lower() in item_text.lower():
                        while current_pos > target_pos:
                            up_btn = item.locator('button[aria-label*="up" i], button[aria-label*="arriba" i]')
                            if up_btn.count() > 0:
                                up_btn.first.click()
                                pause_action(runtime_config, multiplier=0.9)
                                current_pos -= 1
                            else:
                                break
                        break
                except Exception:
                    continue

        return True

    # ========== UTILIDADES ==========

    @staticmethod
    def find_question_container(page, pregunta: str, container_selectors: list[str] | None = None):
        """Busca el contenedor de una pregunta por texto."""
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

        # Fallback: buscar por texto y subir al padre
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
    def auto_detect_and_fill(
        container,
        page,
        valor,
        use_js_click: bool = False,
        runtime_config: dict | None = None,
    ) -> bool:
        """Detecta automáticamente el tipo de campo y lo llena."""
        valor_str = str(valor) if not isinstance(valor, list) else str(valor[0])

        if container.locator('input[type="radio"], [role="radio"]').count() > 0:
            return FillingStrategies.click_option_by_text(
                container, page, valor_str, "radio", use_js_click, runtime_config=runtime_config
            )
        if container.locator('input[type="checkbox"], [role="checkbox"]').count() > 0:
            vals = valor if isinstance(valor, list) else [valor_str]
            return FillingStrategies.click_multiple_options(
                container, page, vals, "checkbox", use_js_click, runtime_config=runtime_config
            )
        if container.locator('textarea').count() > 0:
            return FillingStrategies.fill_textarea(container, valor_str, runtime_config=runtime_config)
        if container.locator('select, [role="combobox"]').count() > 0:
            return FillingStrategies.fill_dropdown(container, page, valor_str, runtime_config=runtime_config)
        if container.locator('input:not([type="hidden"])').count() > 0:
            return FillingStrategies.fill_text(container, valor_str, runtime_config=runtime_config)

        return False

    @staticmethod
    def _fill_text_like_field(locator, valor: str) -> bool:
        """Llena un campo de texto y verifica que el valor haya quedado persistido."""
        expected = str(valor)
        for action in (
            lambda: FillingStrategies._fill_with_playwright(locator, expected),
            lambda: FillingStrategies._fill_with_js(locator, expected),
        ):
            try:
                action()
                final_value = FillingStrategies._read_field_value(locator)
                if FillingStrategies._field_value_matches(final_value, expected):
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
                    if (el.isContentEditable) {
                        return (el.textContent || "").trim();
                    }
                    if ("value" in el) {
                        return (el.value || "").toString().trim();
                    }
                    return (el.textContent || "").trim();
                }"""
            )
            return str(value or "").strip()
        except Exception:
            return ""

    @staticmethod
    def _field_value_matches(actual: str, expected: str) -> bool:
        actual = str(actual or "").strip()
        expected = str(expected or "").strip()
        if actual == expected:
            return True
        if actual.replace(" ", "") == expected.replace(" ", ""):
            return True
        actual_digits = "".join(ch for ch in actual if ch.isdigit())
        expected_digits = "".join(ch for ch in expected if ch.isdigit())
        if actual_digits and expected_digits and actual_digits == expected_digits:
            return True
        return False

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
            aria_checked = (locator.get_attribute("aria-checked") or "").lower()
            if aria_checked == "true":
                return True
            return bool(locator.evaluate("el => Boolean(el.checked)"))
        except Exception:
            return False
