"""
Inputs especiales de Google Forms: fechas, horas, matrices y escalas.
Solo responsabilidad: manejar tipos de campo que no son texto ni opciones simples.
Para agregar soporte a un nuevo tipo especial (ej. slider de rango): solo editar aquí.
"""
import logging

from app.automation.gforms._base import click_control, normalize_match_text, prepare_scope, score_option_candidate
from app.automation.filling_strategies import FillingStrategies
from app.automation.timing import pause_action
from app.utils.fuzzy_matcher import similarity as _similarity

logger = logging.getLogger(__name__)

_IS_ANCESTOR_HIDDEN_JS = (
    "el => { let p = el; while (p) {"
    " if (p.getAttribute && p.getAttribute('aria-hidden') === 'true') return true;"
    " p = p.parentElement; } return false; }"
)
# Same logic as a named JS function body for use inside larger evaluate() strings
_IS_HIDDEN_JS_FN = (
    "node => { let p = node; while (p) {"
    " if (p.getAttribute && p.getAttribute('aria-hidden') === 'true') return true;"
    " p = p.parentElement; } return false; }"
)


def _match_col_index(col_headers: list, target_norm: str) -> int:
    """Retorna el índice de la columna que mejor coincide con target_norm, o -1."""
    best_idx, best_score = -1, 0
    for i, h in enumerate(col_headers):
        h_norm = normalize_match_text(h)
        if not h_norm:
            continue
        if h_norm == target_norm:
            return i
        score = 0
        if target_norm in h_norm or h_norm in target_norm:
            score = len(min(target_norm, h_norm, key=len))
        else:
            r = _similarity(h_norm, target_norm)
            if r > 0.6:
                score = int(r * 100)
        if score > best_score:
            best_score, best_idx = score, i
    return best_idx


class SpecialInputHandler:
    """Maneja fechas, horas, matrices y escalas Likert de Google Forms."""

    def fill_date(self, page, valor: str, container=None, text_writer=None, runtime_config: dict | None = None) -> bool:
        scope = container or page
        prepare_scope(scope)
        partes = FillingStrategies._parse_date(valor)
        if not partes:
            if text_writer:
                return text_writer.write(page, valor, container, tipo="fecha")
            return False
        dia, mes, anio = partes
        try:
            for sel, val in [
                ('[aria-label*="Dia" i], [aria-label*="Día" i], [aria-label*="Day" i]', str(dia)),
                ('[aria-label*="Mes" i], [aria-label*="Month" i]', str(mes)),
                ('[aria-label*="Ano" i], [aria-label*="Año" i], [aria-label*="Year" i]', str(anio)),
            ]:
                try:
                    el = scope.locator(sel).first
                    if el.is_visible(timeout=1000):
                        el.fill(val)
                        pause_action(runtime_config, multiplier=0.6)
                except Exception:
                    pass
            return True
        except Exception:
            return False

    def fill_time(self, page, valor: str, container=None, runtime_config: dict | None = None) -> bool:
        scope = container or page
        prepare_scope(scope)
        partes = str(valor).split(":")
        hora = partes[0].strip() if partes else "12"
        minuto = partes[1].strip() if len(partes) > 1 else "00"
        try:
            for sel, val in [
                ('[aria-label*="Hora" i], [aria-label*="Hour" i]', hora),
                ('[aria-label*="Minuto" i], [aria-label*="Minute" i]', minuto),
            ]:
                try:
                    el = scope.locator(sel).first
                    if el.is_visible(timeout=1000):
                        el.fill(val)
                        pause_action(runtime_config, multiplier=0.6)
                except Exception:
                    pass
            return True
        except Exception:
            return False

    def fill_matrix(self, page, valor, tipo: str, container=None, runtime_config: dict | None = None, opciones: list | None = None) -> bool:
        scope = container or page
        prepare_scope(scope)
        try:
            rows = self._find_matrix_rows(scope, page, container, valor)
            logger.debug("[matriz] %s filas encontradas", len(rows))
            if not rows:
                return False

            role = "checkbox" if tipo == "matriz_checkbox" else "radio"

            # Obtener orden de columnas: primero del parámetro, luego del DOM
            col_headers = list(opciones) if opciones else []
            if not col_headers:
                col_headers = self._find_col_headers(scope)
            if not col_headers and page is not None:
                col_headers = self._find_col_headers(page)
            if col_headers:
                logger.debug("[matriz] columnas: %s", col_headers)

            if isinstance(valor, dict):
                return self._fill_matrix_dict(rows, valor, role, runtime_config, col_headers)
            if isinstance(valor, list):
                return self._fill_matrix_list(rows, valor, role, runtime_config, col_headers)
            if isinstance(valor, (str, int)):
                completadas = sum(
                    1 for row in rows
                    if self._click_in_group(row, str(valor), role, runtime_config, col_headers)
                    and not pause_action(runtime_config, multiplier=0.7)
                )
                return completadas > 0
            return False
        except Exception as e:
            logger.debug("Error matriz: %s", e)
            return False

    def _find_matrix_rows(self, scope, page, container, valor) -> list:
        """Encuentra las filas de la matriz usando múltiples estrategias en cascada."""
        _SEL = ('[role="radiogroup"], [role="group"], '
                'div[class*="ssX1Bd"]:has([role="radio"]), '
                'div[class*="ssX1Bd"]:has([role="checkbox"])')

        def _filter_hidden(candidates):
            visible = []
            for r in candidates:
                try:
                    if not r.evaluate(_IS_ANCESTOR_HIDDEN_JS):
                        visible.append(r)
                except Exception:
                    visible.append(r)
            return visible or candidates

        # Estrategia 1: buscar en el scope dado
        rows = _filter_hidden(scope.locator(_SEL).all())

        # Estrategia 2: fallback a página completa si el container era incorrecto
        if not rows and container and page is not None:
            rows = _filter_hidden(page.locator(_SEL).all())

        # Calcular filas esperadas
        expected = (len(valor) if isinstance(valor, dict)
                    else len(valor) if isinstance(valor, list) else 0)

        # Estrategia 3: si se encontró un único grupo contenedor, expandirlo
        if expected > 0 and len(rows) < expected:
            expanded = self._expand_group_rows(rows, scope, page, expected)
            if expanded:
                rows = expanded

        return rows

    def _expand_group_rows(self, current_rows, scope, page, expected: int) -> list:
        """Expande un grupo contenedor buscando filas individuales dentro."""
        # 3a: radiogroups anidados dentro de los grupos actuales
        nested = []
        for r in current_rows:
            try:
                nested.extend(r.locator('[role="radiogroup"], [role="group"]').all())
            except Exception:
                pass
        if len(nested) >= expected:
            return nested

        # 3b: agrupar radios por elemento padre usando JS (forma más robusta)
        for search_scope in ([scope] if scope is not None else []) + ([page] if page is not None and page is not scope else []):
            rows_by_parent = self._group_by_parent(search_scope)
            if len(rows_by_parent) >= expected:
                return rows_by_parent

        return current_rows

    @staticmethod
    def _group_by_parent(scope) -> list:
        """Marca con data-mrow los padres de cada radio y los retorna como locators."""
        try:
            scope.evaluate(
                """el => {
                    const role = '[role="radio"],[role="checkbox"]';
                    const radios = Array.from(el.querySelectorAll(role));
                    const parents = new Map();
                    for (const r of radios) {
                        const p = r.parentElement;
                        if (p && !parents.has(p)) parents.set(p, parents.size);
                    }
                    for (const [p, i] of parents) p.setAttribute('data-mrow', String(i));
                }"""
            )
            return scope.locator('[data-mrow]').all()
        except Exception:
            return []

    def _fill_matrix_dict(self, rows: list, valor: dict, role: str, runtime_config, col_headers: list | None = None) -> bool:
        """Llena las filas de la matriz usando el dict {fila: columna}."""
        normalized_targets = {
            normalize_match_text(k): (k, v)
            for k, v in valor.items()
            if normalize_match_text(k)
        }
        completadas = 0
        for idx, row in enumerate(rows):
            row_label = self._extract_row_label(row)
            row_norm = normalize_match_text(row_label)

            best_key, best_payload, best_score = "", None, 0
            if row_norm:
                for key_norm, payload in normalized_targets.items():
                    s = self._score_row_match(row_norm, key_norm)
                    if s > best_score:
                        best_score, best_key, best_payload = s, key_norm, payload

            # Fallback por índice solo cuando la fila no tiene label propio
            if (not best_payload or best_score < 600) and not row_norm and idx < len(valor):
                best_payload = list(valor.items())[idx]
                best_key = normalize_match_text(best_payload[0])

            if not best_payload:
                logger.debug("[matriz] fila sin match: '%s'", row_label[:40])
                continue

            _, col_val = best_payload
            vals = col_val if isinstance(col_val, list) else [col_val]
            row_ok = all(self._click_in_group(row, str(cv), role, runtime_config, col_headers) for cv in vals)
            if row_ok:
                completadas += 1
                normalized_targets.pop(best_key, None)
                pause_action(runtime_config, multiplier=0.7)

        return completadas > 0

    def _fill_matrix_list(self, rows: list, valor: list, role: str, runtime_config, col_headers: list | None = None) -> bool:
        """Llena las filas de la matriz usando una lista ordenada de valores."""
        completadas = 0
        for idx, val in enumerate(valor):
            if idx >= len(rows):
                break
            vals = val if isinstance(val, list) else [val]
            row_ok = all(self._click_in_group(rows[idx], str(v), role, runtime_config, col_headers) for v in vals)
            if row_ok:
                completadas += 1
                pause_action(runtime_config, multiplier=0.7)
        return completadas > 0

    @staticmethod
    def _find_col_headers(scope) -> list:
        """Extrae los textos de columna del encabezado visible de la matriz."""
        try:
            result = scope.evaluate(
                f"""el => {{
                    const isHidden = {_IS_HIDDEN_JS_FN};
                    const rows = Array.from(el.querySelectorAll('div[class*="ssX1Bd"]'));
                    const header = rows.find(r =>
                        !r.querySelector('[role="radio"],[role="checkbox"]') && !isHidden(r)
                    );
                    if (!header) return [];
                    return Array.from(header.children)
                        .map(c => (c.innerText || '').trim())
                        .filter(t => t.length > 0);
                }}"""
            )
            return result if isinstance(result, list) else []
        except Exception:
            return []

    def fill_scales(self, page, escalas_con_container: list, runtime_config: dict | None = None) -> int:
        """Responde escalas Likert usando sus contenedores ya identificados."""
        respondidas = 0
        for valor, container in escalas_con_container:
            try:
                scope = container or page
                radios = scope.locator('[role="radio"]').all()
                if not radios:
                    continue
                respuesta = str(valor).lower()
                seleccionado = False

                for radio in radios:
                    if respuesta in (radio.get_attribute("aria-label") or "").lower():
                        radio.click()
                        seleccionado = True
                        break

                if not seleccionado:
                    for radio in radios:
                        if (radio.get_attribute("data-value") or "").lower() == respuesta:
                            radio.click()
                            seleccionado = True
                            break

                if not seleccionado and respuesta.isdigit():
                    idx = int(respuesta) - 1
                    if 0 <= idx < len(radios):
                        radios[idx].click()
                        seleccionado = True

                if seleccionado:
                    respondidas += 1
                    pause_action(runtime_config, multiplier=0.8)
            except Exception:
                continue
        logger.debug("Respondidas %s escalas", respondidas)
        return respondidas

    @staticmethod
    def _click_in_group(row, valor: str, role: str, runtime_config: dict | None = None, col_headers: list | None = None) -> bool:
        controls = row.locator(f'[role="{role}"]').all()
        if not controls:
            return False

        # Google Forms matrices marcan radios con aria-disabled="true" aunque sí son clicables.
        # Preferimos controles realmente activos; si no hay ninguno, usamos todos.
        def _attr(el, name):
            try:
                return el.get_attribute(name)
            except Exception:
                return None

        active = [c for c in controls if _attr(c, "aria-disabled") != "true"]
        candidates = active if active else controls

        target = normalize_match_text(valor)

        # Estrategia 1: match exacto/fuzzy por aria-label o data-value
        for ctrl in candidates:
            label = _attr(ctrl, "aria-label") or _attr(ctrl, "data-value") or ""
            if score_option_candidate([label], valor) >= 1000:
                click_control(ctrl, runtime_config)
                return True

        for ctrl in candidates:
            label = normalize_match_text(_attr(ctrl, "aria-label") or _attr(ctrl, "data-value") or "")
            if target and label and (target in label or label in target):
                click_control(ctrl, runtime_config)
                return True

        best_ctrl, best_ratio = None, 0
        for ctrl in candidates:
            label = normalize_match_text(_attr(ctrl, "aria-label") or _attr(ctrl, "data-value") or "")
            if label:
                ratio = _similarity(label, target)
                if ratio > best_ratio:
                    best_ratio, best_ctrl = ratio, ctrl
        if best_ratio > 0.6 and best_ctrl:
            click_control(best_ctrl, runtime_config)
            return True

        # Estrategia 2: índice por encabezados de columna conocidos
        if col_headers:
            col_idx = _match_col_index(col_headers, target)
            if 0 <= col_idx < len(controls):
                click_control(controls[col_idx], runtime_config)
                return True

        # Estrategia 3: índice numérico directo
        if target.isdigit():
            idx = int(target) - 1
            if 0 <= idx < len(candidates):
                click_control(candidates[idx], runtime_config)
                return True

        return False

    @staticmethod
    def _extract_row_label(row) -> str:
        try:
            aria = (row.get_attribute("aria-label") or "").strip()
            if aria:
                return aria
        except Exception:
            pass

        try:
            # Google Forms suele poner en las opciones: "Fila texto, Opcion texto"
            first_radio = row.locator('[role="radio"], [role="checkbox"]')
            if first_radio.count() > 0:
                radio_aria = (first_radio.first.get_attribute("aria-label") or "").strip()
                if radio_aria and "," in radio_aria:
                    return radio_aria.rsplit(",", 1)[0].strip()
        except Exception:
            pass
        try:
            raw = row.inner_text(timeout=500)
        except Exception:
            raw = ""
        for line in str(raw).splitlines():
            clean = line.strip()
            if clean:
                return clean
        return ""

    @staticmethod
    def _score_row_match(row_norm: str, key_norm: str) -> int:
        if not row_norm or not key_norm:
            return 0
        if row_norm == key_norm:
            return 2000
        if row_norm in key_norm or key_norm in row_norm:
            return 1400

        ratio = _similarity(row_norm, key_norm)
        if ratio > 0.6:
            return int(ratio * 1000)

        return score_option_candidate([row_norm], key_norm)
