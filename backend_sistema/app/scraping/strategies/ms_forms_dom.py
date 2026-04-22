"""
Estrategia DOM para Microsoft Forms: extrae estructura desde el DOM renderizado.
Usado como último fallback cuando la API interna no responde.
Para agregar soporte a un nuevo tipo de pregunta del DOM: agregar bloque en _detect_tipo.
"""
import logging
import time

logger = logging.getLogger(__name__)


class MicrosoftFormsDOMStrategy:
    """Extrae estructura de Microsoft Forms desde el DOM renderizado por Playwright."""

    def extract(self, page) -> dict | None:
        try:
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

            for i in range(question_containers.count()):
                container = question_containers.nth(i)
                try:
                    texto = self._extract_title(container)
                    if not texto:
                        continue
                    tipo, opciones, extra = self._detect_tipo(container)
                    preg_data = {"texto": texto, "tipo": tipo, "obligatoria": False, "opciones": opciones}
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
                "paginas": [{"numero": 1, "preguntas": preguntas, "botones": ["Enviar"]}],
                "total_preguntas": len(preguntas),
                "requiere_login": False,
                "plataforma": "microsoft_forms",
            }
        except Exception as e:
            logger.warning("[MS Forms DOM] Error: %s", e)
            return None

    @staticmethod
    def _extract_title(container) -> str:
        try:
            title_el = container.locator(
                '[class*="question-title"], [class*="questionTitle"], span[class*="text"]'
            ).first
            if title_el.count() > 0:
                return title_el.text_content(timeout=2000).strip()
        except Exception:
            pass
        return ""

    @staticmethod
    def _detect_tipo(container) -> tuple[str, list, dict]:
        """Detecta el tipo de pregunta y extrae opciones y datos extra."""
        radios = container.locator('input[type="radio"], [role="radio"]')
        checkboxes = container.locator('input[type="checkbox"], [role="checkbox"]')

        if radios.count() > 0:
            return MicrosoftFormsDOMStrategy._handle_radio(container, radios)

        if checkboxes.count() > 0:
            labels = container.locator('label, [class*="choice"]')
            opciones = [labels.nth(j).text_content(timeout=1000).strip()
                        for j in range(labels.count())
                        if labels.nth(j).text_content(timeout=1000).strip()]
            return "seleccion_multiple", opciones, {}

        if container.locator('[class*="rating"], [class*="star"]').count() > 0:
            rating_btns = container.locator('[class*="rating"] button, button[aria-posinset]')
            opciones = [str(j + 1) for j in range(rating_btns.count())]
            return "escala_lineal", opciones, {}

        if container.locator('textarea').count() > 0:
            return "parrafo", [], {}
        if container.locator('input[type="date"]').count() > 0:
            return "fecha", [], {}
        if container.locator('input[type="time"]').count() > 0:
            return "hora", [], {}
        if container.locator('input[type="number"]').count() > 0:
            return "numero", [], {}

        if container.locator('select, [role="combobox"]').count() > 0:
            opciones = []
            try:
                opts = container.locator('option, [role="option"]')
                for j in range(opts.count()):
                    txt = opts.nth(j).text_content(timeout=500).strip()
                    if txt and txt not in ("", "Seleccionar", "Select"):
                        opciones.append(txt)
            except Exception:
                pass
            return "desplegable", opciones, {}

        if container.locator('[class*="ranking"], [class*="sortable"]').count() > 0:
            opciones = []
            try:
                items = container.locator('[class*="ranking-item"], [class*="sortable-item"]')
                for j in range(items.count()):
                    txt = items.nth(j).text_content(timeout=500).strip()
                    if txt:
                        opciones.append(txt)
            except Exception:
                pass
            return "ranking", opciones, {}

        if container.locator('input[type="file"]').count() > 0:
            return "archivo", [], {"no_llenar": True}

        return "texto", [], {}

    @staticmethod
    def _handle_radio(container, radios) -> tuple[str, list, dict]:
        radio_groups = container.locator(
            '[class*="likert-row"], [class*="matrix-row"], tr:has(input[type="radio"])'
        )
        if radio_groups.count() > 1:
            filas = []
            for j in range(radio_groups.count()):
                try:
                    row_text = radio_groups.nth(j).locator(
                        'td:first-child, [class*="row-title"]'
                    ).first.text_content(timeout=1000).strip()
                    if row_text:
                        filas.append(row_text)
                except Exception:
                    pass
            opciones = []
            try:
                cols = container.locator('[class*="likert-header"] span, thead th')
                for j in range(cols.count()):
                    txt = cols.nth(j).text_content(timeout=1000).strip()
                    if txt:
                        opciones.append(txt)
            except Exception:
                pass
            extra = {"filas": filas} if filas else {}
            return "likert", opciones, extra

        if radios.count() == 11:
            return "nps", [str(i) for i in range(0, 11)], {}

        labels = container.locator('label, [class*="choice"]')
        opciones = [labels.nth(j).text_content(timeout=1000).strip()
                    for j in range(labels.count())
                    if labels.nth(j).text_content(timeout=1000).strip()]
        return "opcion_multiple", opciones, {}
