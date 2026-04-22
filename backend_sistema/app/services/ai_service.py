"""
Servicio de IA - Factory y gestión de proveedores.
Para registrar un nuevo proveedor: añadir una entrada en _PROVIDER_REGISTRY.
"""
import logging
from flask import current_app
from app.ai.provider import AIProvider
from app.ai.openai_provider import OpenAIProvider
from app.ai.anthropic_provider import AnthropicProvider

logger = logging.getLogger(__name__)

# Registry OCP: agregar nuevo proveedor = una línea aquí.
_PROVIDER_REGISTRY: dict[str, tuple[type, str]] = {
    "openai": (OpenAIProvider, "gpt-4o"),
    "anthropic": (AnthropicProvider, "claude-sonnet-4-20250514"),
}


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
        """Configura proveedores desde la configuración usando _PROVIDER_REGISTRY."""
        key_map = {
            "openai": ("OPENAI_API_KEY", "OPENAI_MODEL"),
            "anthropic": ("ANTHROPIC_API_KEY", "ANTHROPIC_MODEL"),
        }
        for name, (cls, default_model) in _PROVIDER_REGISTRY.items():
            api_key_cfg, model_cfg = key_map.get(name, (f"{name.upper()}_API_KEY", f"{name.upper()}_MODEL"))
            api_key = config.get(api_key_cfg, "")
            if not api_key:
                continue
            try:
                self._providers[name] = cls(
                    api_key=api_key,
                    model=config.get(model_cfg, default_model),
                )
            except ImportError:
                logger.warning("Paquete para proveedor '%s' no instalado, no disponible", name)

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
        if name not in _PROVIDER_REGISTRY:
            raise ValueError(f"Proveedor '{name}' no soportado. Disponibles: {list(_PROVIDER_REGISTRY)}")
        cls, default_model = _PROVIDER_REGISTRY[name]
        self._providers[name] = cls(api_key=api_key, model=model or default_model)

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
