"""
Estrategia de scraping: API interna de Microsoft Forms.
Para agregar soporte a un nuevo tipo de pregunta de la API: editar _parse_question_extras.
Para cambiar la lógica DOM (fallback): editar ms_forms_dom.py.
"""
import re
import json
import requests

from app.constants.question_types import (
    map_ms_forms_type,
    TIPO_LIKERT,
    TIPO_ARCHIVO,
    TIPO_ESCALA_LINEAL,
    TIPO_NPS,
    TIPO_NUMERO,
)
from app.scraping.strategies.ms_forms_dom import MicrosoftFormsDOMStrategy


def _clean_ms_text(value) -> str:
    if value is None:
        return ""
    return str(value).replace("\u00a0", " ").strip()


def _to_num(val):
    """Convierte valor de límite numérico de la API (string o número) a int/float/None."""
    if val is None or val == "":
        return None
    try:
        f = float(val)
        return int(f) if f.is_integer() else f
    except (TypeError, ValueError):
        return None


def _order_key(q: dict) -> float:
    try:
        return float(q.get("order") or q.get("sequenceNumber") or 0)
    except (TypeError, ValueError):
        return 0


def _parse_qi(q: dict) -> dict:
    """Parsea questionInfo a dict, soportando tanto dict como string JSON."""
    qi_raw = q.get("questionInfo")
    if isinstance(qi_raw, dict):
        return qi_raw
    if isinstance(qi_raw, str) and qi_raw:
        try:
            return json.loads(qi_raw)
        except (json.JSONDecodeError, TypeError):
            pass
    return {}


class MicrosoftFormsStrategy:
    """Extrae estructura de Microsoft Forms usando su API interna + fallback DOM."""

    def __init__(self):
        self._dom_strategy = MicrosoftFormsDOMStrategy()

    def extract(self, url: str, html: str = "", page=None) -> dict | None:
        if html:
            result = self._extract_via_api(html, url)
            if result and result["total_preguntas"] > 0:
                print(f"  [MS Forms API] Extraídas {result['total_preguntas']} preguntas")
                return result

        if page and not html:
            html = page.content()
            result = self._extract_via_api(html, url)
            if result and result["total_preguntas"] > 0:
                print(f"  [MS Forms API] Extraídas {result['total_preguntas']} preguntas")
                return result

        if page:
            result = self._dom_strategy.extract(page)
            if result and result["total_preguntas"] > 0:
                print(f"  [MS Forms DOM] Extraídas {result['total_preguntas']} preguntas")
                return result

        return None

    # ── API ────────────────────────────────────────────────────────────────────

    def _extract_via_api(self, html: str, original_url: str) -> dict | None:
        try:
            api_url = self._find_api_url(html)
            if not api_url:
                print("  [MS Forms API] No se encontró API URL en el HTML")
                return None

            print("  [MS Forms API] URL encontrada, consultando...")
            resp = requests.get(api_url, timeout=15, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
            })
            if resp.status_code != 200:
                print(f"  [MS Forms API] Status {resp.status_code}")
                return None

            return self._parse_api_response(resp.json(), original_url)
        except Exception as e:
            print(f"  [MS Forms API] Error: {e}")
            return None

    @staticmethod
    def _find_api_url(html: str) -> str | None:
        pattern = r'(https://forms\.office\.com/formapi/api/[^\s"\'<>]+runtimeForms[^\s"\'<>]*expand=questions[^\s"\'<>]*)'
        matches = re.findall(pattern, html)
        if not matches:
            pattern2 = r'(https://forms\.office\.com/formapi/api/[a-f0-9-]+/users/[a-f0-9-]+/light/runtimeForms\([^)]+\))'
            matches2 = re.findall(pattern2, html)
            if matches2:
                api_url = matches2[0].replace("\\u0027", "'")
                matches = [api_url + "?$expand=questions($expand=choices)"]
        if not matches:
            return None
        url = matches[0]
        return url.replace("\\u0027", "'").replace("\\u0026", "&").replace("&amp;", "&")

    def _parse_api_response(self, data: dict, url: str) -> dict | None:
        try:
            questions = data.get("questions", [])
            if not questions:
                return None

            questions_sorted = sorted(questions, key=_order_key)
            paginas = []
            pagina_actual = {"numero": 1, "preguntas": [], "botones": ["Siguiente"]}

            for q in questions_sorted:
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

                texto = _clean_ms_text(q.get("title") or q.get("questionText"))
                if not texto:
                    continue

                tipo = map_ms_forms_type(q)
                qi = _parse_qi(q)
                obligatoria = bool(q.get("required") or q.get("isRequired") or qi.get("Required"))

                pregunta = {"texto": texto, "tipo": tipo, "obligatoria": obligatoria, "opciones": []}

                if tipo == TIPO_ARCHIVO:
                    pregunta["no_llenar"] = True
                    pagina_actual["preguntas"].append(pregunta)
                    continue

                self._extract_choices(pregunta, q, qi)
                self._parse_question_extras(pregunta, q, qi, tipo)
                pagina_actual["preguntas"].append(pregunta)

            pagina_actual["botones"] = ["Enviar"]
            if pagina_actual["preguntas"]:
                paginas.append(pagina_actual)

            if not paginas:
                return None

            for i, pag in enumerate(paginas):
                pag["numero"] = i + 1
                pag["botones"] = ["Enviar"] if i == len(paginas) - 1 else ["Siguiente"]

            total = sum(len(p["preguntas"]) for p in paginas)
            if total == 0:
                return None

            return {
                "url": url,
                "titulo": _clean_ms_text(data.get("title") or data.get("name")),
                "descripcion": _clean_ms_text(data.get("description") or data.get("subtitle")),
                "paginas": paginas,
                "total_preguntas": total,
                "requiere_login": False,
                "plataforma": "microsoft_forms",
            }
        except Exception as e:
            print(f"  [MS Forms] Error parseando API response: {e}")
            return None

    @staticmethod
    def _extract_choices(pregunta: dict, q: dict, qi: dict):
        for c in q.get("choices", []):
            if isinstance(c, dict):
                opt = _clean_ms_text(c.get("description") or c.get("value") or c.get("text"))
                if opt:
                    pregunta["opciones"].append(opt)
            elif isinstance(c, str):
                cleaned = _clean_ms_text(c)
                if cleaned:
                    pregunta["opciones"].append(cleaned)

        if not pregunta["opciones"]:
            for c in qi.get("Choices", []):
                if isinstance(c, dict):
                    desc = _clean_ms_text(c.get("Description") or c.get("Value"))
                    if desc:
                        pregunta["opciones"].append(desc)
                elif isinstance(c, str):
                    cleaned = _clean_ms_text(c)
                    if cleaned:
                        pregunta["opciones"].append(cleaned)

    @staticmethod
    def _parse_question_extras(pregunta: dict, q: dict, qi: dict, tipo: str):
        if tipo == TIPO_LIKERT:
            filas = []
            for row in qi.get("Rows", qi.get("rows", [])):
                if isinstance(row, dict):
                    rt = _clean_ms_text(row.get("Description") or row.get("title"))
                    if rt:
                        filas.append(rt)
                elif isinstance(row, str):
                    cleaned = _clean_ms_text(row)
                    if cleaned:
                        filas.append(cleaned)
            if not filas:
                for sq in (q.get("subQuestions") or q.get("questions") or []):
                    if isinstance(sq, dict):
                        sq_text = _clean_ms_text(sq.get("title") or sq.get("text"))
                        if sq_text:
                            filas.append(sq_text)
            if filas:
                pregunta["filas"] = filas

        elif tipo == TIPO_ESCALA_LINEAL:
            try:
                length = int(qi.get("Length") or q.get("ratingLength") or 5)
                min_rating = int(qi.get("MinRating") if qi.get("MinRating") is not None else q.get("ratingStartValue", 1))
            except (TypeError, ValueError):
                length, min_rating = 5, 1
            if not pregunta["opciones"]:
                pregunta["opciones"] = [str(i) for i in range(min_rating, min_rating + length)]
            low = _clean_ms_text(qi.get("LeftDescription") or qi.get("FormsProRTLeftDescription") or q.get("ratingLowLabel"))
            high = _clean_ms_text(qi.get("RightDescription") or qi.get("FormsProRTRightDescription") or q.get("ratingHighLabel"))
            if low or high:
                pregunta["etiquetas_escala"] = {"min": low, "max": high}
            shape = _clean_ms_text(qi.get("RatingShape") or q.get("ratingShape") or "star")
            if shape:
                pregunta["forma_escala"] = shape.lower()

        elif tipo == TIPO_NPS:
            if not pregunta["opciones"]:
                pregunta["opciones"] = [str(i) for i in range(0, 11)]
            pregunta["etiquetas_escala"] = {
                "min": _clean_ms_text(q.get("npsLowLabel") or q.get("ratingLowLabel") or qi.get("LeftDescription") or "Nada probable"),
                "max": _clean_ms_text(q.get("npsHighLabel") or q.get("ratingHighLabel") or qi.get("RightDescription") or "Muy probable"),
            }

        elif tipo == TIPO_NUMERO:
            min_val = _to_num(qi.get("NumberMinBoundary")) or _to_num(q.get("minValue") or q.get("min"))
            max_val = _to_num(qi.get("NumberMaxBoundary")) or _to_num(q.get("maxValue") or q.get("max"))
            if min_val is not None or max_val is not None:
                pregunta["validacion"] = {"min": min_val, "max": max_val}
            rule = _clean_ms_text(qi.get("NumberValidationRule"))
            if rule:
                pregunta["validacion_regla"] = rule
