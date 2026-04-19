"""
Scraper auxiliar para Microsoft Forms con IA/HTML como fallback controlado.
"""
import time
from playwright.sync_api import sync_playwright

from app.scraping.base_scraper import BaseScraper
from app.utils.browser_config import get_browser_context_options_from_flask
from app.scraping.strategies.ai_analysis import AIAnalysisStrategy
from app.scraping.strategies.requests_html import RequestsHTMLStrategy
from app.scraping.strategies.microsoft_forms import MicrosoftFormsStrategy
from app.automation.navigation.selectors import detectar_plataforma


class GenericScraper(BaseScraper):
    """Scraper alterno para Microsoft Forms."""

    def __init__(self, ai_service=None):
        self.ai_service = ai_service
        self.html_strategy = RequestsHTMLStrategy()
        self.ai_strategy = AIAnalysisStrategy(ai_service) if ai_service else None
        self.ms_strategy = MicrosoftFormsStrategy()

    def scrape(self, url: str, headless: bool = True) -> dict:
        """Scrapea Microsoft Forms y usa IA solo como apoyo al flujo soportado.

        Cuando se llega aquí es porque el factory decidió (por URL o por
        force_platform) que el scraper correcto es el de MS Forms. Si la URL
        no matchea el patrón estándar, igual intentamos: la estrategia de API
        interna descubre la URL real desde el HTML renderizado.
        """
        detected = detectar_plataforma(url)
        platform_name = "microsoft_forms"
        resultado = self.resultado_vacio(url, platform_name)
        if detected["name"] != "microsoft_forms":
            print(f"  [MS Forms] URL no matchea patrón MS Forms (detectada: {detected['name']}). Forzando scrapeo.")

        print("  [MS Forms] Intentando API interna...")
        api_result = self.ms_strategy.extract(url=url)
        if api_result and api_result["total_preguntas"] > 0:
            return api_result

        ctx_options = get_browser_context_options_from_flask()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(**ctx_options)
            page = context.new_page()
            page.goto(url, wait_until="networkidle")
            time.sleep(3)

            resultado["url"] = page.url
            html = page.content()

            print("  [MS Forms] Intentando con HTML renderizado...")
            ms_result = self.ms_strategy.extract(url=url, html=html, page=page)
            if ms_result and ms_result["total_preguntas"] > 0:
                browser.close()
                return ms_result

            if self.ai_strategy:
                print("  [MS Forms] Analizando con IA como fallback...")
                ai_result = self.ai_strategy.extract(page=page, html=html, url=url)
                if ai_result and ai_result["total_preguntas"] > 0:
                    browser.close()
                    ai_result["plataforma"] = platform_name
                    print(f"  -> IA detectó {ai_result['total_preguntas']} preguntas")
                    return ai_result

            print("  [MS Forms] Fallback final: parsing HTML...")
            html_result = self.html_strategy.extract(html, url)
            if html_result:
                resultado = html_result
                resultado["plataforma"] = platform_name

            browser.close()

        print(f"\n  Scraping Microsoft Forms completado:")
        print(f"    Plataforma: {platform_name}")
        print(f"    Preguntas: {resultado['total_preguntas']}")

        return resultado
