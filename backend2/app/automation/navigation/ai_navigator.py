"""
Navegador inteligente que usa IA para encontrar botones y campos en páginas desconocidas.
"""
import base64
import json
from app.ai.prompts import PROMPT_SISTEMA_NAVEGACION, PROMPT_DETECTAR_BOTONES, PROMPT_DETECTAR_CAMPOS


class AINavigator:
    """Usa IA (visión o análisis HTML) para navegar formularios desconocidos."""

    def __init__(self, ai_service):
        self.ai = ai_service

    def find_navigation_buttons(self, page) -> list[dict]:
        """Detecta botones de navegación usando IA."""
        try:
            html = page.content()
            # Truncar HTML si es muy largo
            if len(html) > 15000:
                html = html[:15000] + "\n... [TRUNCADO]"

            provider = self.ai.get_provider()
            result = provider.chat_completion(
                system_prompt=PROMPT_SISTEMA_NAVEGACION,
                user_prompt=PROMPT_DETECTAR_BOTONES.format(html_content=html),
                json_mode=True,
                max_tokens=1000,
            )
            data = json.loads(result)
            return data.get("botones", [])
        except Exception as e:
            print(f"    AI Navigator - Error detectando botones: {e}")
            return []

    def find_field_selector(self, page, pregunta: str, tipo: str, valor: str) -> dict | None:
        """Usa IA para encontrar el selector CSS de un campo específico."""
        try:
            html = page.content()
            if len(html) > 15000:
                html = html[:15000] + "\n... [TRUNCADO]"

            provider = self.ai.get_provider()
            result = provider.chat_completion(
                system_prompt=PROMPT_SISTEMA_NAVEGACION,
                user_prompt=PROMPT_DETECTAR_CAMPOS.format(
                    html_content=html,
                    pregunta=pregunta,
                    tipo=tipo,
                    valor=valor,
                ),
                json_mode=True,
                max_tokens=500,
            )
            return json.loads(result)
        except Exception as e:
            print(f"    AI Navigator - Error detectando campo: {e}")
            return None

    def click_next_with_ai(self, page) -> bool:
        """Intenta encontrar y clickear el botón siguiente usando IA."""
        buttons = self.find_navigation_buttons(page)
        for btn in buttons:
            if btn.get("tipo") in ("siguiente", "next"):
                try:
                    selector = btn.get("selector_css", "")
                    if selector:
                        element = page.locator(selector).first
                        if element.is_visible():
                            element.click()
                            return True
                except Exception:
                    continue
        return False

    def click_submit_with_ai(self, page) -> bool:
        """Intenta encontrar y clickear el botón enviar usando IA."""
        buttons = self.find_navigation_buttons(page)
        for btn in buttons:
            if btn.get("tipo") in ("enviar", "submit"):
                try:
                    selector = btn.get("selector_css", "")
                    if selector:
                        element = page.locator(selector).first
                        if element.is_visible():
                            element.click()
                            return True
                except Exception:
                    continue
        return False

    def fill_field_with_ai(self, page, pregunta: str, tipo: str, valor: str) -> bool:
        """Usa IA para encontrar y llenar un campo."""
        field_info = self.find_field_selector(page, pregunta, tipo, valor)
        if not field_info:
            return False

        try:
            selector = field_info.get("selector_css", "")
            accion = field_info.get("accion", "")
            element = page.locator(selector).first

            if accion == "click":
                element.click()
                return True
            elif accion == "fill":
                element.fill(str(field_info.get("valor_para_accion", valor)))
                return True
            elif accion == "select":
                element.select_option(str(field_info.get("valor_para_accion", valor)))
                return True
        except Exception as e:
            print(f"    AI Navigator - Error llenando campo: {e}")

        return False
