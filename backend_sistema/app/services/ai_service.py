"""
Servicio de IA - Factory y gestión de proveedores.
"""
from flask import current_app
from app.ai.provider import AIProvider
from app.ai.openai_provider import OpenAIProvider
from app.ai.anthropic_provider import AnthropicProvider


class AIService:
    """Gestiona proveedores de IA, permite intercambiarlos dinámicamente."""

    def __init__(self):
        self._providers: dict[str, AIProvider] = {}
        self._active_provider_name: str | None = None

    def init_app(self, app):
        """Inicializa con la configuración de la app Flask."""
        with app.app_context():
            self._setup_from_config(app.config)

    def _setup_from_config(self, config):
        """Configura proveedores desde la configuración."""
        # OpenAI
        openai_key = config.get("OPENAI_API_KEY", "")
        if openai_key:
            self._providers["openai"] = OpenAIProvider(
                api_key=openai_key,
                model=config.get("OPENAI_MODEL", "gpt-4o"),
            )

        # Anthropic
        anthropic_key = config.get("ANTHROPIC_API_KEY", "")
        if anthropic_key:
            try:
                self._providers["anthropic"] = AnthropicProvider(
                    api_key=anthropic_key,
                    model=config.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
                )
            except ImportError:
                print("  anthropic package no instalado, proveedor no disponible")

        # Establecer proveedor activo
        default = config.get("DEFAULT_AI_PROVIDER", "openai")
        if default in self._providers:
            self._active_provider_name = default
        elif self._providers:
            self._active_provider_name = next(iter(self._providers))

    def get_provider(self, name: str | None = None) -> AIProvider:
        """Obtiene un proveedor de IA por nombre, o el activo por defecto."""
        if name and name in self._providers:
            return self._providers[name]

        if self._active_provider_name and self._active_provider_name in self._providers:
            return self._providers[self._active_provider_name]

        raise ValueError("No hay proveedor de IA configurado. Configura OPENAI_API_KEY o ANTHROPIC_API_KEY en .env")

    def set_active_provider(self, name: str):
        """Cambia el proveedor activo."""
        if name not in self._providers:
            raise ValueError(f"Proveedor '{name}' no disponible. Disponibles: {list(self._providers.keys())}")
        self._active_provider_name = name

    def add_provider(self, name: str, api_key: str, model: str = ""):
        """Agrega o actualiza un proveedor en runtime."""
        if name == "openai":
            self._providers["openai"] = OpenAIProvider(
                api_key=api_key,
                model=model or "gpt-4o",
            )
        elif name == "anthropic":
            self._providers["anthropic"] = AnthropicProvider(
                api_key=api_key,
                model=model or "claude-sonnet-4-20250514",
            )
        else:
            raise ValueError(f"Proveedor '{name}' no soportado")

    def list_providers(self) -> list[dict]:
        """Lista proveedores disponibles."""
        result = []
        for name, provider in self._providers.items():
            result.append({
                "name": name,
                "model": provider.get_model(),
                "is_active": name == self._active_provider_name,
            })
        return result

    @property
    def active_provider_name(self) -> str | None:
        return self._active_provider_name
