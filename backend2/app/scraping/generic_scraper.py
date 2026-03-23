"""
Scraper genérico que usa estrategias específicas por plataforma + IA como fallback.
"""
import time
from flask import current_app
from playwright.sync_api import sync_playwright

from app.scraping.base_scraper import BaseScraper
from app.scraping.strategies.ai_analysis import AIAnalysisStrategy
from app.scraping.strategies.requests_html import RequestsHTMLStrategy
from app.scraping.strategies.microsoft_forms import MicrosoftFormsStrategy
from app.automation.navigation.selectors import detectar_plataforma


class GenericScraper(BaseScraper):
    """Scraper genérico con estrategias específicas por plataforma."""

    def __init__(self, ai_service=None):
        self.ai_service = ai_service
        self.html_strategy = RequestsHTMLStrategy()
        self.ai_strategy = AIAnalysisStrategy(ai_service) if ai_service else None
        self.ms_strategy = MicrosoftFormsStrategy()

    def scrape(self, url: str, headless: bool = True) -> dict:
        """Scrapea cualquier formulario web."""
        platform = detectar_plataforma(url)
        resultado = self.resultado_vacio(url, platform["name"])

        try:
            locale = current_app.config.get("BROWSER_LOCALE", "es-PE")
            timezone = current_app.config.get("BROWSER_TIMEZONE", "America/Lima")
            vp_w = current_app.config.get("BROWSER_VIEWPORT_WIDTH", 1280)
            vp_h = current_app.config.get("BROWSER_VIEWPORT_HEIGHT", 720)
        except RuntimeError:
            locale, timezone, vp_w, vp_h = "es-PE", "America/Lima", 1280, 720

        # Para Microsoft Forms, intentar API primero (sin necesidad de Playwright)
        if platform["name"] == "microsoft_forms":
            print("  [MS Forms] Intentando API interna...")
            api_result = self.ms_strategy.extract(url=url)
            if api_result and api_result["total_preguntas"] > 0:
                return api_result

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(
                locale=locale,
                timezone_id=timezone,
                viewport={"width": vp_w, "height": vp_h},
            )
            page = context.new_page()
            page.goto(url, wait_until="networkidle")
            time.sleep(3)

            resultado["url"] = page.url
            html = page.content()

            # Microsoft Forms: intentar con HTML del navegador + DOM renderizado
            if platform["name"] == "microsoft_forms":
                print("  [MS Forms] Intentando con HTML renderizado...")
                ms_result = self.ms_strategy.extract(url=url, html=html, page=page)
                if ms_result and ms_result["total_preguntas"] > 0:
                    browser.close()
                    return ms_result

            # Intentar con IA (para cualquier plataforma)
            if self.ai_strategy:
                print(f"  [Generic] Analizando con IA ({platform['name']})...")
                ai_result = self.ai_strategy.extract(page=page, html=html, url=url)
                if ai_result and ai_result["total_preguntas"] > 0:
                    browser.close()
                    ai_result["plataforma"] = platform["name"]
                    print(f"  -> IA detectó {ai_result['total_preguntas']} preguntas")
                    return ai_result

            # Fallback: HTML parsing
            print("  [Generic] Fallback: parsing HTML...")
            html_result = self.html_strategy.extract(html, url)
            if html_result:
                resultado = html_result
                resultado["plataforma"] = platform["name"]

            browser.close()

        print(f"\n  Scraping genérico completado:")
        print(f"    Plataforma: {platform['name']}")
        print(f"    Preguntas: {resultado['total_preguntas']}")

        return resultado
