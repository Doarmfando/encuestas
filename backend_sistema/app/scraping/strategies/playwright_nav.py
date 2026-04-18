"""
Estrategia de scraping: Navegacion con Playwright.
Navega pagina por pagina detectando preguntas del DOM.
"""
import time
import re

from app.automation.navigation.button_detector import detectar_botones, llenar_dummy_pagina
from app.utils.question_inference import infer_short_answer_type, SHORT_ANSWER_INPUT_SELECTORS


class PlaywrightNavStrategy:
    """Scrapea navegando pagina por pagina con Playwright."""

    def extract(self, page, url: str) -> dict:
        """Extrae la estructura navegando por las paginas del formulario."""
        resultado = {
            "url": url,
            "titulo": "",
            "descripcion": "",
            "paginas": [],
            "total_preguntas": 0,
            "requiere_login": False,
            "plataforma": "google_forms",
        }

        page.goto(url, wait_until="networkidle")
        time.sleep(2)

        try:
            titulo_el = page.locator('[role="heading"]').first
            if titulo_el.count() > 0:
                resultado["titulo"] = titulo_el.inner_text().strip()
        except Exception:
            pass

        try:
            page.wait_for_selector('[role="listitem"]', timeout=2000)
        except Exception:
            pass

        num_pagina = 1
        max_paginas = 20
        paginas_vistas = set()

        form_title = (resultado.get("titulo") or "").strip().lower()
        form_desc = (resultado.get("descripcion") or "").strip().lower()

        def _has_meaningful_text(texto: str) -> bool:
            if not texto:
                return False
            clean = " ".join(str(texto).lower().split())
            if form_title:
                clean = clean.replace(form_title, "")
            if form_desc:
                clean = clean.replace(form_desc, "")
            for token in (
                "siguiente", "atras", "enviar", "borrar formulario", "borrar",
                "submit", "back", "next", "previous", "clear form",
            ):
                clean = clean.replace(token, "")
            clean = re.sub(r"(pagina|page)\s*\d+(\s*de\s*\d+)?", "", clean)
            clean = re.sub(r"[^a-z0-9]+", "", clean)
            return len(clean) >= 10

        while num_pagina <= max_paginas:
            try:
                botones_detectados = detectar_botones(page, url)
            except Exception:
                botones_detectados = []

            try:
                page_text_snapshot = ""
                items_check = page.locator('[role="listitem"]').all()
                textos_items = []
                for item in items_check:
                    try:
                        texto = item.inner_text(timeout=1000).strip()[:50]
                        if texto:
                            textos_items.append(texto)
                    except Exception:
                        pass
                page_text = ""
                try:
                    page_text = page.locator("form").inner_text(timeout=800)
                except Exception:
                    try:
                        page_text = page.evaluate("document.body ? document.body.innerText : ''")
                    except Exception:
                        page_text = ""
                page_text_snapshot = page_text
                hash_pagina = hash((
                    tuple(sorted(textos_items)),
                    tuple(botones_detectados),
                    (page_text or "")[:200],
                ))
            except Exception:
                page_text_snapshot = ""
                hash_pagina = hash((str(num_pagina), tuple(botones_detectados)))

            if hash_pagina in paginas_vistas:
                break
            paginas_vistas.add(hash_pagina)

            pagina_data = {"numero": num_pagina, "preguntas": [], "botones": []}

            seen_in_page = set()
            items = page.locator('[role="listitem"]').all()
            for item in items:
                pregunta = self._extraer_pregunta(item)
                if pregunta:
                    texto_key = pregunta["texto"].strip().lower()[:80]
                    if texto_key in seen_in_page:
                        continue
                    seen_in_page.add(texto_key)
                    pagina_data["preguntas"].append(pregunta)
                    resultado["total_preguntas"] += 1

            pagina_data["botones"] = botones_detectados
            has_meaningful_text = _has_meaningful_text(page_text_snapshot)
            if not pagina_data["preguntas"] and not has_meaningful_text:
                if "Siguiente" in pagina_data["botones"]:
                    try:
                        btn = page.locator(
                            'span:has-text("Siguiente"), [role="button"]:has-text("Siguiente")'
                        ).first
                        btn.click()
                        time.sleep(2)
                        page.wait_for_load_state("networkidle")
                        time.sleep(1)
                    except Exception:
                        break
                    num_pagina += 1
                    continue
                if not pagina_data["botones"]:
                    break

            resultado["paginas"].append(pagina_data)

            if "Siguiente" in pagina_data["botones"]:
                if pagina_data["preguntas"]:
                    llenar_dummy_pagina(page)
                    time.sleep(0.5)
                try:
                    btn = page.locator(
                        'span:has-text("Siguiente"), [role="button"]:has-text("Siguiente")'
                    ).first
                    btn.click()
                    time.sleep(2)
                    page.wait_for_load_state("networkidle")
                    time.sleep(1)
                except Exception:
                    break
                num_pagina += 1
            else:
                break

        return resultado

    def _extraer_pregunta(self, item) -> dict | None:
        """Extrae una pregunta de un elemento del DOM."""
        try:
            texto = item.inner_text().strip()
            if not texto or len(texto) < 3:
                return None

            pregunta = {
                "texto": "",
                "tipo": "desconocido",
                "obligatoria": False,
                "opciones": [],
            }

            lineas = texto.split("\n")
            pregunta["texto"] = lineas[0].strip().replace(" *", "")
            pregunta["obligatoria"] = "*" in texto

            tiene_otro = False
            try:
                otro_input = item.locator(
                    '[aria-label="Otro"], [aria-label="Other"], input[type="text"][aria-label*="Otro"]'
                )
                if otro_input.count() > 0:
                    tiene_otro = True
            except Exception:
                pass

            radios = item.locator('[role="radio"]').all()
            if radios:
                is_scale = self._detect_scale(item, radios)
                if is_scale:
                    pregunta["tipo"] = "escala_lineal"
                    for radio in radios:
                        label = radio.get_attribute("aria-label") or radio.get_attribute("data-value") or ""
                        if label.strip():
                            pregunta["opciones"].append(label.strip())
                    try:
                        scale_labels = item.locator('[class*="scale"] span, [class*="ratingLabel"]').all()
                        if len(scale_labels) >= 2:
                            pregunta["etiquetas_escala"] = {
                                "min": scale_labels[0].inner_text().strip(),
                                "max": scale_labels[-1].inner_text().strip(),
                            }
                    except Exception:
                        pass
                else:
                    pregunta["tipo"] = "opcion_multiple"
                    for radio in radios:
                        label = radio.get_attribute("aria-label") or ""
                        if label.strip():
                            pregunta["opciones"].append(label.strip())
                    if not pregunta["opciones"]:
                        for lbl in item.locator(
                            ".docssharedWizToggleLabeledContent, [data-value]"
                        ).all():
                            value = lbl.inner_text().strip() or lbl.get_attribute("data-value") or ""
                            if value and value not in pregunta["opciones"]:
                                pregunta["opciones"].append(value)

                if tiene_otro:
                    pregunta["tiene_otro"] = True
                    if "Otro" not in pregunta["opciones"]:
                        pregunta["opciones"].append("Otro")
                return pregunta

            checks = item.locator('[role="checkbox"]').all()
            if checks:
                pregunta["tipo"] = "seleccion_multiple"
                for check in checks:
                    label = check.get_attribute("aria-label") or ""
                    if label.strip():
                        pregunta["opciones"].append(label.strip())
                if tiene_otro:
                    pregunta["tiene_otro"] = True
                    if "Otro" not in pregunta["opciones"]:
                        pregunta["opciones"].append("Otro")
                return pregunta

            try:
                rows = item.locator('[role="radiogroup"], [role="group"]').all()
                if len(rows) > 1:
                    first_row_radios = rows[0].locator('[role="radio"]').all()
                    first_row_checks = rows[0].locator('[role="checkbox"]').all()
                    pregunta["tipo"] = "matriz_checkbox" if first_row_checks else "matriz"
                    for row_option in (first_row_radios or first_row_checks):
                        label = row_option.get_attribute("aria-label") or ""
                        if label.strip() and label.strip() not in pregunta["opciones"]:
                            pregunta["opciones"].append(label.strip())
                    filas = []
                    for row in rows:
                        try:
                            row_label = row.get_attribute("aria-label") or ""
                            if row_label.strip():
                                filas.append(row_label.strip())
                        except Exception:
                            pass
                    if filas:
                        pregunta["filas"] = filas
                    return pregunta
            except Exception:
                pass

            try:
                date_inputs = item.locator(
                    'input[type="date"], [aria-label*="Día"], [aria-label*="Day"], '
                    '[aria-label*="Mes"], [aria-label*="Month"], [aria-label*="Año"], [aria-label*="Year"]'
                )
                if date_inputs.count() > 0:
                    pregunta["tipo"] = "fecha"
                    return pregunta
            except Exception:
                pass

            try:
                time_inputs = item.locator(
                    'input[type="time"], [aria-label*="Hora"], [aria-label*="Hour"], '
                    '[aria-label*="Minuto"], [aria-label*="Minute"]'
                )
                if time_inputs.count() > 0:
                    pregunta["tipo"] = "hora"
                    return pregunta
            except Exception:
                pass

            try:
                has_file = False
                file_inputs = item.locator('input[type="file"]')
                for idx in range(file_inputs.count()):
                    try:
                        if file_inputs.nth(idx).is_visible(timeout=200):
                            has_file = True
                            break
                    except Exception:
                        continue

                if not has_file:
                    for sel in ('button:has-text("Agregar archivo")', 'button:has-text("Add file")'):
                        try:
                            btn = item.locator(sel).first
                            if btn.count() > 0 and btn.is_visible(timeout=200):
                                has_file = True
                                break
                        except Exception:
                            continue

                if has_file:
                    pregunta["tipo"] = "archivo"
                    pregunta["no_llenar"] = True
                    return pregunta
            except Exception:
                pass

            if item.locator('textarea').count() > 0:
                pregunta["tipo"] = "parrafo"
                return pregunta

            if item.locator(", ".join(SHORT_ANSWER_INPUT_SELECTORS)).count() > 0:
                field_hints = self._collect_input_hints(item, SHORT_ANSWER_INPUT_SELECTORS)
                pregunta["tipo"] = infer_short_answer_type(pregunta["texto"], field_hints)
                return pregunta

            if item.locator('[role="listbox"]').count() > 0:
                pregunta["tipo"] = "desplegable"
                try:
                    options = item.locator('[role="option"]').all()
                    for opt in options:
                        value = opt.get_attribute("data-value") or opt.inner_text().strip()
                        if value and value not in pregunta["opciones"] and value != "Elige":
                            pregunta["opciones"].append(value)
                except Exception:
                    pass
                return pregunta

            if len(texto) > 5:
                pregunta["tipo"] = "informativo"
                return pregunta

            return None
        except Exception:
            return None

    def _detect_scale(self, item, radios) -> bool:
        """Detecta si un grupo de radios es una escala lineal."""
        try:
            if len(radios) < 3 or len(radios) > 11:
                return False
            values = []
            for radio in radios:
                value = radio.get_attribute("data-value") or radio.get_attribute("aria-label") or ""
                value = value.strip()
                if value.isdigit():
                    values.append(int(value))
            if len(values) >= 3:
                sorted_vals = sorted(values)
                return all(sorted_vals[i] == sorted_vals[0] + i for i in range(len(sorted_vals)))
            return False
        except Exception:
            return False

    @staticmethod
    def _collect_input_hints(scope, selectors: list[str], max_inputs: int = 3) -> str:
        """Extrae attrs utiles para inferir si un input corto es numerico."""
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
