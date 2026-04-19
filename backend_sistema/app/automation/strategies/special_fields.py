"""
Campos especiales: dropdown, fecha, hora, matriz y ranking.
Para agregar soporte a un nuevo formato de fecha: extender _parse_date.
Para agregar un nuevo tipo de dropdown: extender fill_dropdown.
"""
from app.automation.timing import pause_action
from app.automation.strategies.text_filler import TextFiller


def _parse_date(valor: str) -> tuple | None:
    """Parsea fecha string -> (dia, mes, año)."""
    try:
        valor = str(valor).strip()
        if "-" in valor and len(valor) >= 8:
            partes = valor.split("-")
            if len(partes[0]) == 4:
                return int(partes[2]), int(partes[1]), int(partes[0])
            return int(partes[0]), int(partes[1]), int(partes[2])
        elif "/" in valor:
            partes = valor.split("/")
            return int(partes[0]), int(partes[1]), int(partes[2])
    except Exception:
        pass
    return None


class SpecialFieldFiller:
    """Llena dropdowns, fechas, horas, matrices y rankings."""

    _parse_date = staticmethod(_parse_date)

    @staticmethod
    def fill_dropdown(container, page, valor: str, trigger_selectors: list[str] | None = None,
                      runtime_config: dict | None = None) -> bool:
        selects = container.locator('select')
        if selects.count() > 0:
            try:
                selects.first.select_option(label=valor)
                return True
            except Exception:
                pass

        if trigger_selectors is None:
            trigger_selectors = [
                '[role="combobox"]', '[role="listbox"]',
                '[class*="dropdown"]', 'button[class*="select"]',
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
                    page.keyboard.press("Escape")
                    pause_action(runtime_config, multiplier=0.7)
                except Exception:
                    pass
        return False

    @staticmethod
    def fill_date(container, valor: str,
                  day_selectors: list[str] | None = None,
                  month_selectors: list[str] | None = None,
                  year_selectors: list[str] | None = None,
                  runtime_config: dict | None = None) -> bool:
        partes = _parse_date(valor)
        if not partes:
            return TextFiller.fill_text(container, valor, runtime_config=runtime_config)
        dia, mes, anio = partes

        try:
            date_input = container.locator('input[type="date"]').first
            if date_input.is_visible(timeout=1000):
                date_input.fill(f"{anio:04d}-{mes:02d}-{dia:02d}")
                return True
        except Exception:
            pass

        if day_selectors is None:
            day_selectors = [
                'input[type="date"]',
                '[aria-label*="Día" i]', '[aria-label*="Day" i]', 'input[placeholder*="DD"]',
            ]
        if month_selectors is None:
            month_selectors = ['[aria-label*="Mes" i]', '[aria-label*="Month" i]', 'input[placeholder*="MM"]']
        if year_selectors is None:
            year_selectors = [
                '[aria-label*="Año" i]', '[aria-label*="Year" i]',
                'input[placeholder*="AAAA"]', 'input[placeholder*="YYYY"]',
            ]

        filled_any = False
        for sel, val_str in [
            (day_selectors, str(dia)),
            (month_selectors, str(mes)),
            (year_selectors, str(anio)),
        ]:
            for s in sel:
                if 'type="date"' in s:
                    continue
                try:
                    el = container.locator(s).first
                    if el.is_visible(timeout=1000):
                        el.click()
                        pause_action(runtime_config, multiplier=0.6)
                        el.fill(val_str)
                        filled_any = True
                        break
                except Exception:
                    continue
        return filled_any

    @staticmethod
    def fill_time(container, valor: str,
                  hour_selectors: list[str] | None = None,
                  minute_selectors: list[str] | None = None,
                  runtime_config: dict | None = None) -> bool:
        partes = str(valor).split(":")
        hora = partes[0].strip() if partes else "12"
        minuto = partes[1].strip() if len(partes) > 1 else "00"

        try:
            time_input = container.locator('input[type="time"]').first
            if time_input.is_visible(timeout=1000):
                time_input.fill(f"{hora}:{minuto}")
                return True
        except Exception:
            pass

        if hour_selectors is None:
            hour_selectors = ['[aria-label*="Hora" i]', '[aria-label*="Hour" i]', 'input[placeholder*="HH"]']
        if minute_selectors is None:
            minute_selectors = ['[aria-label*="Minuto" i]', '[aria-label*="Minute" i]', 'input[placeholder*="MM"]']

        filled_any = False
        for sel_list, val_str in [(hour_selectors, hora), (minute_selectors, minuto)]:
            for sel in sel_list:
                try:
                    el = container.locator(sel).first
                    if el.is_visible(timeout=1000):
                        el.click()
                        pause_action(runtime_config, multiplier=0.6)
                        el.fill(val_str)
                        filled_any = True
                        break
                except Exception:
                    continue

        if not filled_any:
            dropdowns = container.locator('select, [role="combobox"]')
            if dropdowns.count() >= 2:
                try:
                    dropdowns.nth(0).select_option(value=hora)
                    pause_action(runtime_config, multiplier=0.7)
                    dropdowns.nth(1).select_option(value=minuto)
                    return True
                except Exception:
                    pass

        return filled_any or TextFiller.fill_text(container, valor, runtime_config=runtime_config)

    @staticmethod
    def fill_matrix(container, page, valor, row_selector: str = '[role="radiogroup"]',
                    use_js_click: bool = False, runtime_config: dict | None = None) -> bool:
        from app.automation.strategies.option_clicker import OptionClicker
        rows = container.locator(row_selector)
        row_count = rows.count()

        if row_count == 0:
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
                        SpecialFieldFiller._click_in_row(row, page, str(col_val), use_js_click, runtime_config=runtime_config)
                        pause_action(runtime_config, multiplier=0.7)
                        break
        elif isinstance(valor, list):
            for i, val in enumerate(valor):
                if i < row_count:
                    if isinstance(val, list):
                        for v in val:
                            SpecialFieldFiller._click_in_row(rows.nth(i), page, str(v), use_js_click, role="checkbox", runtime_config=runtime_config)
                    else:
                        SpecialFieldFiller._click_in_row(rows.nth(i), page, str(val), use_js_click, runtime_config=runtime_config)
                    pause_action(runtime_config, multiplier=0.7)
        else:
            for i in range(row_count):
                SpecialFieldFiller._click_in_row(rows.nth(i), page, str(valor), use_js_click, runtime_config=runtime_config)
                pause_action(runtime_config, multiplier=0.7)
        return True

    @staticmethod
    def fill_ranking(container, page, valor: list, runtime_config: dict | None = None) -> bool:
        ranking_items = container.locator(
            '[class*="ranking-item"], [class*="sortable-item"], [class*="drag-item"], [draggable="true"]'
        )
        item_count = ranking_items.count()
        if item_count == 0 or not isinstance(valor, list):
            return False

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

    @staticmethod
    def _click_in_row(row, page, valor: str, use_js_click: bool = False,
                       role: str = "radio", runtime_config: dict | None = None) -> bool:
        inputs = row.locator(f'input[type="{role}"], [role="{role}"]')
        count = inputs.count()
        if count == 0:
            return False

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
