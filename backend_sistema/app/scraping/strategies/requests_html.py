"""
Estrategia de scraping: Parsing HTML directo.
Fallback que no requiere Playwright - parsea el HTML con regex.
"""
import logging
import re
import json

logger = logging.getLogger(__name__)


class RequestsHTMLStrategy:
    """Parsea el HTML directamente como fallback."""

    def extract(self, html: str, url: str = "") -> dict | None:
        """Intenta extraer estructura de la encuesta parseando HTML crudo.

        Returns:
            dict con estructura o None si no encontró nada.
        """
        resultado = {
            "url": url,
            "titulo": "",
            "descripcion": "",
            "paginas": [],
            "total_preguntas": 0,
            "requiere_login": False,
            "plataforma": "google_forms",
        }

        logger.info("[HTML Fallback] Parseando HTML directo...")

        # Extraer título
        titulo_match = re.search(r'<meta property="og:title" content="([^"]+)"', html)
        if titulo_match:
            resultado["titulo"] = titulo_match.group(1)

        # Extraer descripción
        desc_match = re.search(r'<meta property="og:description" content="([^"]+)"', html)
        if desc_match:
            resultado["descripcion"] = desc_match.group(1)

        # Extraer datos del script data-params
        preguntas = []
        params_matches = re.findall(r'data-params="([^"]+)"', html)
        for params in params_matches:
            try:
                decoded = params.replace("&quot;", '"').replace("&amp;", "&")
                data = json.loads(decoded)
                if isinstance(data, list) and len(data) > 1:
                    texto = data[1] if len(data) > 1 else ""
                    if texto and isinstance(texto, str):
                        preguntas.append({
                            "texto": texto,
                            "tipo": "desconocido",
                            "obligatoria": False,
                            "opciones": [],
                        })
            except Exception:
                pass

        if preguntas:
            resultado["paginas"] = [{
                "numero": 1,
                "preguntas": preguntas,
                "botones": ["Enviar"],
            }]
            resultado["total_preguntas"] = len(preguntas)
            return resultado

        return None
