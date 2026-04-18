"""
Estrategia de scraping: Análisis con IA.
Usa un proveedor de IA para entender la estructura de cualquier formulario.
"""
import base64
import json
from app.ai.prompts import PROMPT_SISTEMA_SCRAPING, PROMPT_ANALIZAR_HTML


class AIAnalysisStrategy:
    """Usa IA para analizar la estructura de cualquier formulario web."""

    def __init__(self, ai_service):
        self.ai = ai_service

    def extract(self, page=None, html: str = "", url: str = "") -> dict | None:
        """Analiza la página usando IA (HTML + opcionalmente screenshot).

        Args:
            page: Playwright page (opcional, para screenshots).
            html: HTML de la página.
            url: URL del formulario.

        Returns:
            dict con estructura del formulario o None.
        """
        if not html and page:
            html = page.content()

        if not html:
            return None

        try:
            provider = self.ai.get_provider()

            # Truncar HTML si es muy largo
            html_truncated = html
            if len(html) > 20000:
                html_truncated = html[:20000] + "\n... [TRUNCADO]"

            # Intentar con visión si tenemos página
            if page:
                return self._extract_with_vision(page, html_truncated, url, provider)

            # Solo con HTML
            return self._extract_from_html(html_truncated, url, provider)

        except Exception as e:
            print(f"  [AI Analysis] Error: {e}")
            return None

    def _extract_with_vision(self, page, html: str, url: str, provider) -> dict | None:
        """Extrae usando screenshot + HTML."""
        try:
            screenshot_bytes = page.screenshot(full_page=True)
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

            prompt = (
                PROMPT_ANALIZAR_HTML.format(html_content=html, url=url)
                + "\n\nAdemás, te adjunto un screenshot de la página para mayor contexto visual."
            )

            result = provider.analyze_image(
                image_base64=screenshot_b64,
                prompt=prompt,
                max_tokens=4000,
            )

            data = json.loads(result)
            return self._normalizar_resultado(data, url)
        except Exception as e:
            print(f"  [AI Vision] Fallback a solo HTML: {e}")
            return self._extract_from_html(html, url, provider)

    def _extract_from_html(self, html: str, url: str, provider) -> dict | None:
        """Extrae solo desde HTML."""
        try:
            result = provider.chat_completion(
                system_prompt=PROMPT_SISTEMA_SCRAPING,
                user_prompt=PROMPT_ANALIZAR_HTML.format(html_content=html, url=url),
                json_mode=True,
                max_tokens=4000,
            )

            data = json.loads(result)
            return self._normalizar_resultado(data, url)
        except Exception as e:
            print(f"  [AI HTML] Error: {e}")
            return None

    def _normalizar_resultado(self, data: dict, url: str) -> dict | None:
        """Normaliza el resultado de la IA al formato estándar."""
        if not data.get("paginas"):
            return None

        resultado = {
            "url": url,
            "titulo": data.get("titulo", ""),
            "descripcion": data.get("descripcion", ""),
            "paginas": [],
            "total_preguntas": 0,
            "requiere_login": False,
            "plataforma": data.get("plataforma_detectada", "unsupported"),
        }

        for pag in data["paginas"]:
            pagina = {
                "numero": pag.get("numero", len(resultado["paginas"]) + 1),
                "preguntas": [],
                "botones": pag.get("botones", ["Enviar"]),
            }
            for preg in pag.get("preguntas", []):
                pregunta = {
                    "texto": preg.get("texto", ""),
                    "tipo": preg.get("tipo", "texto"),
                    "obligatoria": preg.get("obligatoria", False),
                    "opciones": preg.get("opciones", []),
                }
                pagina["preguntas"].append(pregunta)
                resultado["total_preguntas"] += 1

            resultado["paginas"].append(pagina)

        return resultado if resultado["total_preguntas"] > 0 else None
