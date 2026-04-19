"""
Scraper especializado para Google Forms.
Combina múltiples estrategias: FB_DATA, Playwright y HTML fallback.
"""
from copy import deepcopy
import re
import time
from playwright.sync_api import sync_playwright

_NUMBERING_RE = re.compile(r'^\d+[\.\)\-]+\s*')
_WHITESPACE_RE = re.compile(r'\s+')

from app.constants.question_types import TIPO_INFORMATIVO, TIPO_MATRIZ, TIPO_MATRIZ_CHECKBOX
from app.scraping.base_scraper import BaseScraper
from app.utils.browser_config import get_browser_context_options_from_flask
from app.scraping.strategies.fb_data import FBDataStrategy
from app.scraping.strategies.playwright_nav import PlaywrightNavStrategy
from app.scraping.strategies.requests_html import RequestsHTMLStrategy


class GoogleFormsScraper(BaseScraper):
    """Scraper especializado para Google Forms con 3 estrategias."""

    def __init__(self):
        self.fb_strategy = FBDataStrategy()
        self.pw_strategy = PlaywrightNavStrategy()
        self.html_strategy = RequestsHTMLStrategy()

    def scrape(self, url: str, headless: bool = True) -> dict:
        """Scrapea un Google Form usando múltiples estrategias."""
        resultado = self.resultado_vacio(url, "google_forms")

        ctx_options = get_browser_context_options_from_flask()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(**ctx_options)
            page = context.new_page()
            page.goto(url, wait_until="networkidle")
            time.sleep(2)

            # Detectar login requerido
            if "accounts.google.com" in page.url:
                resultado["requiere_login"] = True
                browser.close()
                return resultado

            resultado["url"] = page.url

            # ============ ESTRATEGIA 1: FB_PUBLIC_LOAD_DATA_ ============
            html = page.content()
            resultado_fb = self.fb_strategy.extract(html, resultado["url"])

            # ============ ESTRATEGIA 2: Navegación Playwright ============
            print("  [Playwright] Navegación directa...")
            resultado_pw = self.pw_strategy.extract(page, resultado["url"])
            print(f"    -> {resultado_pw['total_preguntas']} preguntas en {len(resultado_pw['paginas'])} páginas")

            browser.close()

        # ============ COMBINAR RESULTADOS ============
        resultado = self._combinar_estrategias(resultado_fb, resultado_pw, html, resultado)

        print(f"\n  Scraping completado:")
        print(f"    Páginas: {len(resultado['paginas'])}")
        print(f"    Preguntas: {resultado['total_preguntas']}")

        return resultado

    def _combinar_estrategias(self, resultado_fb, resultado_pw, html, resultado_base):
        """Combina los resultados de las diferentes estrategias."""
        if resultado_fb and resultado_pw:
            fb_paginas = len(resultado_fb["paginas"])
            pw_paginas = len(resultado_pw["paginas"])
            fb_preguntas = resultado_fb["total_preguntas"]
            pw_preguntas = resultado_pw["total_preguntas"]
            fb_score = self._score_resultado(resultado_fb)
            pw_score = self._score_resultado(resultado_pw)
            fb_ok = self._is_structurally_complete(resultado_fb)
            pw_ok = self._is_structurally_complete(resultado_pw)

            print(
                "\n  Comparando: "
                f"FB_DATA={fb_preguntas}preg/{fb_paginas}pág/score={fb_score} "
                f"vs Playwright={pw_preguntas}preg/{pw_paginas}pág/score={pw_score}"
            )

            if fb_ok and not pw_ok:
                resultado = self._merge_metadata(deepcopy(resultado_fb), resultado_pw)
                print("  -> FB_DATA como base estructuralmente completa; Playwright queda de apoyo")
            elif pw_ok and not fb_ok:
                resultado = self._merge_metadata(deepcopy(resultado_pw), resultado_fb)
                print("  -> Playwright como base estructuralmente completa; FB_DATA incompleto")
            else:
                principal, secundario, principal_nombre = (
                    (resultado_fb, resultado_pw, "FB_DATA")
                    if fb_score >= pw_score
                    else (resultado_pw, resultado_fb, "Playwright")
                )
                resultado = self._combinar_resultados(deepcopy(principal), secundario)
                resultado = self._merge_metadata(resultado, secundario)
                print(f"  -> {principal_nombre} como base por score estructural")
        elif resultado_fb:
            resultado = resultado_fb
            print(f"\n  Usando solo FB_DATA")
        elif resultado_pw["total_preguntas"] > 0:
            resultado = resultado_pw
            print(f"\n  Usando solo Playwright")
        else:
            # Fallback: parsing HTML directo
            print("\n  Ningún método capturó preguntas, usando fallback HTML...")
            html_result = self.html_strategy.extract(html, resultado_base["url"])
            resultado = html_result if html_result else resultado_base

        resultado["plataforma"] = "google_forms"
        return resultado

    def _is_structurally_complete(self, resultado: dict | None) -> bool:
        """Valida si la estructura es suficientemente buena para priorizarla."""
        if not resultado or resultado.get("total_preguntas", 0) <= 0:
            return False

        for pregunta in self._iter_preguntas(resultado):
            tipo = pregunta.get("tipo", "")
            if tipo == TIPO_INFORMATIVO:
                continue
            if not str(pregunta.get("texto", "")).strip():
                return False
            if tipo in (TIPO_MATRIZ, TIPO_MATRIZ_CHECKBOX):
                if not pregunta.get("opciones") or not pregunta.get("filas"):
                    return False
        return True

    def _score_resultado(self, resultado: dict | None) -> int:
        """Puntúa resultados dando prioridad a preguntas completas y matrices válidas."""
        if not resultado:
            return -10000

        total = resultado.get("total_preguntas", 0) or 0
        paginas = len(resultado.get("paginas", []) or [])
        if total <= 0:
            return -1000

        vacias = 0
        matrices_sin_opciones = 0
        matrices_sin_filas = 0

        for pregunta in self._iter_preguntas(resultado):
            tipo = pregunta.get("tipo", "")
            if tipo == TIPO_INFORMATIVO:
                continue
            if not str(pregunta.get("texto", "")).strip():
                vacias += 1
            if tipo in (TIPO_MATRIZ, TIPO_MATRIZ_CHECKBOX):
                if not pregunta.get("opciones"):
                    matrices_sin_opciones += 1
                if not pregunta.get("filas"):
                    matrices_sin_filas += 1

        score = total * 100 + paginas * 15
        score -= vacias * 350
        score -= matrices_sin_opciones * 250
        score -= matrices_sin_filas * 180
        if vacias == 0:
            score += 80
        if matrices_sin_opciones == 0 and matrices_sin_filas == 0:
            score += 40
        return score

    @staticmethod
    def _iter_preguntas(resultado: dict):
        for pagina in resultado.get("paginas", []) or []:
            for pregunta in pagina.get("preguntas", []) or []:
                yield pregunta

    @staticmethod
    def _merge_metadata(principal: dict, secundario: dict | None) -> dict:
        """Completa metadatos sin alterar la estructura elegida."""
        if not secundario:
            return principal
        if not principal.get("titulo") and secundario.get("titulo"):
            principal["titulo"] = secundario["titulo"]
        if not principal.get("descripcion") and secundario.get("descripcion"):
            principal["descripcion"] = secundario["descripcion"]
        if principal.get("paginas"):
            last_buttons = principal["paginas"][-1].get("botones") or []
            if "Enviar" not in last_buttons:
                principal["paginas"][-1]["botones"] = list(dict.fromkeys(last_buttons + ["Enviar"]))
            principal["total_preguntas"] = sum(len(p.get("preguntas", [])) for p in principal["paginas"])
        return principal

    @staticmethod
    def _normalize_key(texto: str) -> str:
        """Normaliza texto de pregunta para comparación. Usa la primera línea limpia."""
        first_line = texto.split("\n")[0].strip().lower().rstrip("*").strip()
        first_line = _NUMBERING_RE.sub("", first_line)
        return _WHITESPACE_RE.sub(" ", first_line).strip()[:60]

    def _match_fb_to_pw(self, fb_key: str, pw_keys: set) -> str | None:
        """Busca si una pregunta de FB_DATA coincide con alguna de Playwright."""
        # Una key vacía matchea con startswith() cualquier string — nunca es un match real
        if not fb_key:
            return None
        if fb_key in pw_keys:
            return fb_key
        # Prefix match: "caso 1:" matchea "caso 1: durante su servicio..."
        for pk in pw_keys:
            if not pk:
                continue
            if fb_key.startswith(pk) or pk.startswith(fb_key):
                return pk
        return None

    def _redistribuir_en_paginas(self, fb_result, pw_result):
        """Redistribuye preguntas de FB_DATA en la estructura de páginas de Playwright."""
        resultado = self.resultado_vacio(fb_result["url"], "google_forms")
        resultado["titulo"] = fb_result["titulo"] or pw_result["titulo"]
        resultado["descripcion"] = fb_result["descripcion"] or pw_result["descripcion"]

        todas_fb = []
        for pag in fb_result["paginas"]:
            for preg in pag["preguntas"]:
                todas_fb.append(preg)

        # Usar primera línea como key para Playwright
        preguntas_pw_keys = set()
        for pag in pw_result["paginas"]:
            for preg in pag["preguntas"]:
                preguntas_pw_keys.add(self._normalize_key(preg["texto"]))

        # FB por texto: mapear con primera línea
        fb_por_texto = {}
        for preg in todas_fb:
            key = self._normalize_key(preg["texto"])
            fb_por_texto[key] = preg

        paginas_finales = []

        for pag_pw in pw_result["paginas"]:
            nueva_pagina = {
                "numero": len(paginas_finales) + 1,
                "preguntas": [],
                "botones": pag_pw["botones"],
            }
            for preg_pw in pag_pw["preguntas"]:
                pw_key = self._normalize_key(preg_pw["texto"])
                # Buscar la versión FB_DATA (tiene más info) con prefix match
                matched_fb = None
                for fb_key, fb_preg in fb_por_texto.items():
                    if not fb_key:  # key vacía matchea todo con startswith — nunca es real
                        continue
                    if fb_key == pw_key or fb_key.startswith(pw_key) or pw_key.startswith(fb_key):
                        matched_fb = fb_preg
                        break
                if matched_fb:
                    preg_final = matched_fb.copy()
                    # Mantener texto de Playwright (corto) para que el filler matchee con el DOM
                    # pero guardar la descripción completa de FB_DATA
                    preg_final["texto"] = preg_pw["texto"]
                    preg_final["descripcion_completa"] = matched_fb["texto"]
                    if not preg_final["opciones"] and preg_pw["opciones"]:
                        preg_final["opciones"] = preg_pw["opciones"]
                    nueva_pagina["preguntas"].append(preg_final)
                else:
                    nueva_pagina["preguntas"].append(preg_pw)

            paginas_finales.append(nueva_pagina)

        # Agregar preguntas de FB_DATA que NO existen en ninguna página de Playwright
        # Solo si FB tiene significativamente más preguntas (posibles preguntas perdidas)
        fb_matched_keys = set()
        for pag in paginas_finales:
            for preg in pag["preguntas"]:
                fb_matched_keys.add(self._normalize_key(preg["texto"]))

        huerfanas_reales = []
        for preg in todas_fb:
            key = self._normalize_key(preg["texto"])
            if key not in fb_matched_keys and not self._match_fb_to_pw(key, preguntas_pw_keys):
                huerfanas_reales.append(preg)

        if huerfanas_reales:
            print(f"    {len(huerfanas_reales)} preguntas hu?rfanas de FB_DATA agregadas a ?ltima p?gina")
            if paginas_finales:
                paginas_finales[-1]["preguntas"].extend(huerfanas_reales)
            else:
                paginas_finales.append({
                    "numero": 1,
                    "preguntas": huerfanas_reales,
                    "botones": ["Enviar"],
                })

        for i, pag in enumerate(paginas_finales):
            pag["numero"] = i + 1
        if paginas_finales:
            last_buttons = paginas_finales[-1].get("botones") or []
            if "Enviar" not in last_buttons:
                paginas_finales[-1]["botones"] = list(dict.fromkeys(last_buttons + ["Enviar"]))

        resultado["paginas"] = paginas_finales
        resultado["total_preguntas"] = sum(len(p["preguntas"]) for p in paginas_finales)
        return resultado

    def _combinar_resultados(self, principal, secundario):
        """Combina dos resultados, principal como base."""
        if not secundario:
            return self._merge_metadata(principal, None)

        textos_principal = set()
        for pag in principal["paginas"]:
            for preg in pag["preguntas"]:
                textos_principal.add(self._normalize_key(preg["texto"]))

        preguntas_extra = []
        for pag in secundario["paginas"]:
            for preg in pag["preguntas"]:
                key = self._normalize_key(preg["texto"])
                if key and not self._match_fb_to_pw(key, textos_principal):
                    preguntas_extra.append(preg)

        if preguntas_extra:
            print(f"    Combinando: {len(preguntas_extra)} preguntas extra del método secundario")
            if principal["paginas"]:
                idx = max(0, len(principal["paginas"]) - 1)
                nueva_pagina = {
                    "numero": idx + 1,
                    "preguntas": preguntas_extra,
                    "botones": ["Siguiente"],
                }
                principal["paginas"].insert(idx, nueva_pagina)
                for i, pag in enumerate(principal["paginas"]):
                    pag["numero"] = i + 1

        if not principal["titulo"] and secundario["titulo"]:
            principal["titulo"] = secundario["titulo"]

        if principal.get("paginas"):
            last_buttons = principal["paginas"][-1].get("botones") or []
            if "Enviar" not in last_buttons:
                principal["paginas"][-1]["botones"] = list(dict.fromkeys(last_buttons + ["Enviar"]))
            principal["total_preguntas"] = sum(len(p["preguntas"]) for p in principal["paginas"])

        return principal
