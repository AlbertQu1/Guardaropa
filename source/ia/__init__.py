import os

from dotenv import load_dotenv

from source.ia.base import IAProvider

load_dotenv()

_provider: IAProvider | None = None


def get_provider() -> IAProvider:
    global _provider
    if _provider is None:
        nombre = os.environ.get("IA_PROVIDER", "gemini")
        if nombre == "gemini":
            from source.ia.gemini import GeminiProvider
            _provider = GeminiProvider()
        else:
            raise ValueError(f"IA_PROVIDER desconocido: {nombre}")
    return _provider
