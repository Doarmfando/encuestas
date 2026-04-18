"""
Proveedor de IA: Anthropic (Claude)
"""
import base64

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

from app.ai.provider import AIProvider


class AnthropicProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        if not HAS_ANTHROPIC:
            raise ImportError("pip install anthropic")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        json_mode: bool = False,
    ) -> str:
        # Anthropic no tiene json_mode nativo, lo instruimos en el prompt
        if json_mode and "JSON" not in system_prompt:
            system_prompt += "\n\nIMPORTANTE: Responde SOLO con JSON válido, sin markdown ni texto adicional."

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
        )
        return response.content[0].text

    def analyze_image(
        self,
        image_base64: str,
        prompt: str,
        max_tokens: int = 4000,
    ) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_base64,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ],
        )
        return response.content[0].text

    def get_name(self) -> str:
        return "anthropic"

    def get_model(self) -> str:
        return self.model
