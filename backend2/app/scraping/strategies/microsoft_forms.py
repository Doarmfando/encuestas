"""
Estrategia de scraping: Microsoft Forms.
Usa la API interna de Microsoft Forms para extraer la estructura completa.
"""
import re
import json
import requests

from app.constants.question_types import map_ms_forms_type, TIPO_LIKERT, TIPO_ARCHIVO, TIPO_ESCALA_LINEAL, TIPO_NPS, TIPO_NUMERO


class MicrosoftFormsStrategy:
    """Extrae estructura de Microsoft Forms usando su API interna."""

    def extract(self, url: str, html: str = "", page=None) -> dict | None:
        """Extrae la estructura del formulario de Microsoft Forms.

        Intenta 3 métodos:
        1. API URL encontrada en el HTML renderizado
        2. API construida desde IDs en el HTML
        3. Parsear el DOM renderizado (fallback)
        """
        # Si tenemos HTML, buscar la API URL directa
        if html:
            result = self._extract_via_api_url_from_html(html, url)
            if result and result["total_preguntas"] > 0:
                print(f"  [MS Forms API] Extraídas {result['total_preguntas']} preguntas")
                return result

        # Si tenemos page (Playwright), obtener HTML y reintentar
        if page and not html:
            html = page.content()
            result = self._extract_via_api_url_from_html(html, url)
            if result and result["total_preguntas"] > 0:
                print(f"  [MS Forms API] Extraídas {result['total_preguntas']} preguntas")
                return result

        # Fallback: DOM renderizado
        if page:
            result = self._extract_from_rendered(page)
            if result and result["total_preguntas"] > 0:
                print(f"  [MS Forms DOM] Extraídas {result['total_preguntas']} preguntas")
                return result

        return None

    def _extract_via_api_url_from_html(self, html: str, original_url: str) -> dict | None:
        """Busca la API URL en el HTML y la consulta directamente."""
        try:
            # Buscar la URL de la API con runtimeForms en el HTML
            # La URL puede tener unicode escapes (\\u0027) y $expand
            pattern = r'(https://forms\.office\.com/formapi/api/[^\s"\'<>]+runtimeForms[^\s"\'<>]*expand=questions[^\s"\'<>]*)'
            matches = re.findall(pattern, html)

            if not matches:
                # Intentar buscar solo la base de la API y construir el expand
                pattern2 = r'(https://forms\.office\.com/formapi/api/[a-f0-9-]+/users/[a-f0-9-]+/light/runtimeForms\([^)]+\))'
                matches2 = re.findall(pattern2, html)
                if matches2:
                    api_url = matches2[0]
                    api_url = api_url.replace("\\u0027", "'")
                    api_url += "?$expand=questions($expand=choices)"
                    matches = [api_url]

            if not matches:
                print("  [MS Forms API] No se encontró API URL en el HTML")
                return None

            # Limpiar la URL (decodificar unicode escapes)
            api_url = matches[0]
            api_url = api_url.replace("\\u0027", "'")
            api_url = api_url.replace("\\u0026", "&")
            api_url = api_url.replace("&amp;", "&")

            print(f"  [MS Forms API] URL encontrada, consultando...")
            resp = requests.get(api_url, timeout=15, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
            })

            if resp.status_code != 200:
                print(f"  [MS Forms API] Status {resp.status_code}")
                return None

            data = resp.json()
            return self._parse_api_response(data, original_url)

        except Exception as e:
            print(f"  [MS Forms API] Error: {e}")
            return None

    def _parse_api_response(self, data: dict, url: str) -> dict | None:
        """Parsea la respuesta de la API de MS Forms."""
        try:
            titulo = data.get("title", "") or data.get("name", "")
            descripcion = data.get("description", "") or data.get("subtitle", "")
            questions = data.get("questions", [])

            if not questions:
                return None

            # Detectar secciones/páginas (MS Forms usa "sections" o pageBreak en questions)
            paginas = []
            pagina_actual = {"numero": 1, "preguntas": [], "botones": ["Siguiente"]}

            for q in questions:
                # Detectar separador de página/sección
                q_type = (q.get("type", "") or "").lower()
                if q_type in ("section", "pagebreak", "sectionheader"):
                    if pagina_actual["preguntas"]:
                        paginas.append(pagina_actual)
                        pagina_actual = {
                            "numero": len(paginas) + 1,
                            "preguntas": [],
                            "botones": ["Siguiente"],
                        }
                    continue

                texto = q.get("title", "") or q.get("questionText", "")
                if not texto:
                    continue

                tipo = map_ms_forms_type(q)

                pregunta = {
                    "texto": texto.strip(),
                    "tipo": tipo,
                    "obligatoria": q.get("isRequired", False) or q.get("required", False),
                    "opciones": [],
                }

                # Archivo: marcar como no llenable
                if tipo == TIPO_ARCHIVO:
                    pregunta["no_llenar"] = True
                    pagina_actual["preguntas"].append(pregunta)
                    continue

                # Extraer opciones - primero de choices expandidos
                choices = q.get("choices", [])
                if choices:
                    for c in choices:
                        if isinstance(c, dict):
                            opt = c.get("description", "") or c.get("value", "") or c.get("text", "")
                            if opt:
                                pregunta["opciones"].append(opt.strip())
                        elif isinstance(c, str):
                            pregunta["opciones"].append(c.strip())

                # Si no hay choices, buscar en questionInfo (JSON string con Choices)
                if not pregunta["opciones"]:
                    question_info = q.get("questionInfo", "")
                    if question_info and isinstance(question_info, str):
                        try:
                            qi = json.loads(question_info)
                            for c in qi.get("Choices", []):
                                desc = c.get("Description", "").strip().replace("\u00a0", "")
                                if desc:
                                    pregunta["opciones"].append(desc)

                            # Extraer filas de Likert/Matrix desde questionInfo
                            if tipo == TIPO_LIKERT:
                                filas = []
                                for row in qi.get("Rows", qi.get("rows", [])):
                                    if isinstance(row, dict):
                                        row_text = row.get("Description", "") or row.get("title", "")
                                        if row_text:
                                            filas.append(row_text.strip())
                                    elif isinstance(row, str):
                                        filas.append(row.strip())
                                if filas:
                                    pregunta["filas"] = filas

                        except (json.JSONDecodeError, TypeError):
                            pass

                # Likert/Matrix: extraer filas de subquestions si existen
                if tipo == TIPO_LIKERT:
                    subquestions = q.get("subQuestions", q.get("questions", []))
                    if subquestions and not pregunta.get("filas"):
                        filas = []
                        for sq in subquestions:
                            if isinstance(sq, dict):
                                sq_text = sq.get("title", "") or sq.get("text", "")
                                if sq_text:
                                    filas.append(sq_text.strip())
                        if filas:
                            pregunta["filas"] = filas

                # Para escalas/rating, extraer rango
                if tipo == TIPO_ESCALA_LINEAL:
                    rating_start = q.get("ratingStartValue", 1)
                    rating_end = q.get("ratingEndValue", 5)
                    rating_shape = q.get("ratingShape", "star")
                    if not pregunta["opciones"]:
                        pregunta["opciones"] = [str(i) for i in range(rating_start, rating_end + 1)]
                    # Guardar labels de escala si existen
                    low_label = q.get("ratingLowLabel", "")
                    high_label = q.get("ratingHighLabel", "")
                    if low_label or high_label:
                        pregunta["etiquetas_escala"] = {
                            "min": low_label,
                            "max": high_label,
                        }

                # NPS: 0-10 con labels
                if tipo == TIPO_NPS:
                    if not pregunta["opciones"]:
                        pregunta["opciones"] = [str(i) for i in range(0, 11)]
                    nps_low = q.get("npsLowLabel", q.get("ratingLowLabel", "Nada probable"))
                    nps_high = q.get("npsHighLabel", q.get("ratingHighLabel", "Muy probable"))
                    pregunta["etiquetas_escala"] = {"min": nps_low, "max": nps_high}

                # Hora: no necesita opciones especiales
                # Número: extraer validaciones si existen
                if tipo == TIPO_NUMERO:
                    min_val = q.get("minValue", q.get("min", None))
                    max_val = q.get("maxValue", q.get("max", None))
                    if min_val is not None or max_val is not None:
                        pregunta["validacion"] = {
                            "min": min_val,
                            "max": max_val,
                        }

                pagina_actual["preguntas"].append(pregunta)

            # Última página tiene "Enviar"
            pagina_actual["botones"] = ["Enviar"]
            if pagina_actual["preguntas"]:
                paginas.append(pagina_actual)

            # Si solo hay una página, simplificar
            if not paginas:
                return None

            # Asegurar que solo la última tenga Enviar
            for i, pag in enumerate(paginas):
                pag["numero"] = i + 1
                if i < len(paginas) - 1:
                    pag["botones"] = ["Siguiente"]
                else:
                    pag["botones"] = ["Enviar"]

            total = sum(len(p["preguntas"]) for p in paginas)
            if total == 0:
                return None

            return {
                "url": url,
                "titulo": titulo,
                "descripcion": descripcion,
                "paginas": paginas,
                "total_preguntas": total,
                "requiere_login": False,
                "plataforma": "microsoft_forms",
            }

        except Exception as e:
            print(f"  [MS Forms] Error parseando API response: {e}")
            return None

    def _extract_from_rendered(self, page) -> dict | None:
        """Extrae la estructura del DOM renderizado por Playwright."""
        try:
            import time
            page.wait_for_selector('[class*="question"], [data-automation-id]', timeout=10000)
            time.sleep(2)

            titulo = ""
            try:
                titulo = page.locator('h1, [class*="formTitle"], [class*="title"]').first.text_content(timeout=3000)
            except Exception:
                pass

            preguntas = []
            question_containers = page.locator(
                '[class*="question-container"], '
                '[class*="office-form-question"], '
                '[data-automation-id*="question"]'
            )

            count = question_containers.count()
            for i in range(count):
                container = question_containers.nth(i)
                try:
                    texto = ""
                    title_el = container.locator(
                        '[class*="question-title"], '
                        '[class*="questionTitle"], '
                        'span[class*="text"]'
                    ).first
                    if title_el.count() > 0:
                        texto = title_el.text_content(timeout=2000).strip()

                    if not texto:
                        continue

                    tipo = "texto"
                    opciones = []
                    extra = {}

                    radios = container.locator('input[type="radio"], [role="radio"]')
                    checkboxes = container.locator('input[type="checkbox"], [role="checkbox"]')

                    if radios.count() > 0:
                        # Detectar si es likert/matrix (múltiples grupos de radios)
                        radio_groups = container.locator('[class*="likert-row"], [class*="matrix-row"], tr:has(input[type="radio"])')
                        if radio_groups.count() > 1:
                            tipo = "likert"
                            filas = []
                            for j in range(radio_groups.count()):
                                try:
                                    row_text = radio_groups.nth(j).locator('td:first-child, [class*="row-title"]').first.text_content(timeout=1000).strip()
                                    if row_text:
                                        filas.append(row_text)
                                except Exception:
                                    pass
                            if filas:
                                extra["filas"] = filas
                            # Opciones de columnas
                            try:
                                cols = container.locator('[class*="likert-header"] span, thead th')
                                for j in range(cols.count()):
                                    txt = cols.nth(j).text_content(timeout=1000).strip()
                                    if txt:
                                        opciones.append(txt)
                            except Exception:
                                pass
                        else:
                            # Detectar NPS (0-10 con 11 opciones)
                            if radios.count() == 11:
                                tipo = "nps"
                                opciones = [str(i) for i in range(0, 11)]
                            else:
                                tipo = "opcion_multiple"
                                labels = container.locator('label, [class*="choice"]')
                                for j in range(labels.count()):
                                    txt = labels.nth(j).text_content(timeout=1000).strip()
                                    if txt:
                                        opciones.append(txt)

                    elif checkboxes.count() > 0:
                        tipo = "seleccion_multiple"
                        labels = container.locator('label, [class*="choice"]')
                        for j in range(labels.count()):
                            txt = labels.nth(j).text_content(timeout=1000).strip()
                            if txt:
                                opciones.append(txt)

                    elif container.locator('[class*="rating"], [class*="star"]').count() > 0:
                        tipo = "escala_lineal"
                        # Extraer botones de rating
                        rating_btns = container.locator('[class*="rating"] button, button[aria-posinset]')
                        for j in range(rating_btns.count()):
                            opciones.append(str(j + 1))

                    elif container.locator('textarea').count() > 0:
                        tipo = "parrafo"

                    elif container.locator('input[type="date"]').count() > 0:
                        tipo = "fecha"

                    elif container.locator('input[type="time"]').count() > 0:
                        tipo = "hora"

                    elif container.locator('input[type="number"]').count() > 0:
                        tipo = "numero"

                    elif container.locator('select, [role="combobox"]').count() > 0:
                        tipo = "desplegable"
                        try:
                            opts = container.locator('option, [role="option"]')
                            for j in range(opts.count()):
                                txt = opts.nth(j).text_content(timeout=500).strip()
                                if txt and txt not in ("", "Seleccionar", "Select"):
                                    opciones.append(txt)
                        except Exception:
                            pass

                    elif container.locator('[class*="ranking"], [class*="sortable"]').count() > 0:
                        tipo = "ranking"
                        try:
                            items = container.locator('[class*="ranking-item"], [class*="sortable-item"]')
                            for j in range(items.count()):
                                txt = items.nth(j).text_content(timeout=500).strip()
                                if txt:
                                    opciones.append(txt)
                        except Exception:
                            pass

                    elif container.locator('input[type="file"]').count() > 0:
                        tipo = "archivo"
                        extra["no_llenar"] = True

                    preg_data = {
                        "texto": texto,
                        "tipo": tipo,
                        "obligatoria": False,
                        "opciones": opciones,
                    }
                    preg_data.update(extra)
                    preguntas.append(preg_data)
                except Exception:
                    continue

            if not preguntas:
                return None

            return {
                "url": "",
                "titulo": titulo or "",
                "descripcion": "",
                "paginas": [{
                    "numero": 1,
                    "preguntas": preguntas,
                    "botones": ["Enviar"],
                }],
                "total_preguntas": len(preguntas),
                "requiere_login": False,
                "plataforma": "microsoft_forms",
            }

        except Exception as e:
            print(f"  [MS Forms DOM] Error: {e}")
            return None
