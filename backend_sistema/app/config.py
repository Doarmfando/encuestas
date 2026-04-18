"""
Configuración centralizada de la aplicación.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-prod")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/encuestas_mejorado"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # AI - OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

    # AI - Anthropic
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    # AI defaults
    DEFAULT_AI_PROVIDER = os.getenv("DEFAULT_AI_PROVIDER", "openai")
    AI_TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0.7"))
    AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "4000"))

    # Browser
    BROWSER_LOCALE = "es-PE"
    BROWSER_TIMEZONE = "America/Lima"
    BROWSER_VIEWPORT_WIDTH = 1280
    BROWSER_VIEWPORT_HEIGHT = 720

    # Execution
    MAX_ENCUESTAS = 500
    PAUSA_MIN = 3.0
    PAUSA_MAX = 8.0

    # Export
    EXPORT_DIR = os.getenv("EXPORT_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "exports"))
