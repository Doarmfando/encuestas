"""
Interfaz abstracta para proveedores de IA.
"""
from abc import ABC, abstractmethod


class AIProvider(ABC):
    """Interfaz base para proveedores de IA."""

    @abstractmethod
    def chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        json_mode: bool = False,
    ) -> str:
        """Envía un mensaje al modelo y retorna la respuesta como string."""
        ...

    @abstractmethod
    def analyze_image(
        self,
        image_base64: str,
        prompt: str,
        max_tokens: int = 4000,
    ) -> str:
        """Analiza una imagen y retorna la respuesta como string."""
        ...

    @abstractmethod
    def get_name(self) -> str:
        """Retorna el nombre del proveedor."""
        ...

    @abstractmethod
    def get_model(self) -> str:
        """Retorna el modelo en uso."""
        ...
