"""Cliente SDK Google Gemini Pro para OmniSpec AI.

Gestiona la conexión con Google Gemini Pro (gemini-1.5-flash),
incluyendo streaming, timeout de 27s, y detección de rate limits.

Attributes:
    DEFAULT_MODEL: Modelo por defecto (gemini-1.5-flash).
    DEFAULT_TEMPERATURE: Temperatura de generación (0.7).
    MAX_OUTPUT_TOKENS: Tokens máximos de respuesta (8192).
    REQUEST_TIMEOUT: Timeout de request en segundos (27).
"""

import os
from typing import Any, Generator

DEFAULT_MODEL = "gemini-2.0-flash"
DEFAULT_TEMPERATURE = 0.7
MAX_OUTPUT_TOKENS = 8192
TOP_P = 0.9
TOP_K = 40
REQUEST_TIMEOUT = 27


class MissingAPIKeyError(Exception):
    """Raised cuando GEMINI_API_KEY no está configurada."""
    pass


class RateLimitError(Exception):
    """Raised cuando Gemini Pro retorna HTTP 429."""

    def __init__(self, retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after}s")


class GeminiClientError(Exception):
    """Raised para errores genéricos del cliente Gemini."""
    pass


class GeminiClient:
    """Cliente para Google Gemini Pro SDK.

    Configura el modelo gemini-1.5-flash con parámetros optimizados
    para generación de especificaciones SDD.

    Attributes:
        model_name: Nombre del modelo configurado.
        is_available: True si la API key está presente y el cliente inicializado.
    """

    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL):
        """Inicializa el cliente Gemini Pro.

        Args:
            api_key: API key de Google. Si None, lee de GEMINI_API_KEY env var.
            model: Nombre del modelo a usar.

        Raises:
            MissingAPIKeyError: Si no se proporciona API key.
        """
        self.model_name = model
        self._api_key = api_key if api_key is not None else os.environ.get("GEMINI_API_KEY", "")
        self._model = None
        self._is_available = False

        if self._api_key:
            self._initialize_client()

    @property
    def is_available(self) -> bool:
        """Indica si el cliente está listo para generar."""
        return self._is_available

    def _initialize_client(self) -> None:
        """Inicializa el SDK de Google Generative AI."""
        try:
            import google.generativeai as genai

            genai.configure(api_key=self._api_key)

            generation_config = {
                "temperature": DEFAULT_TEMPERATURE,
                "max_output_tokens": MAX_OUTPUT_TOKENS,
                "top_p": TOP_P,
                "top_k": TOP_K,
            }

            self._model = genai.GenerativeModel(
                model_name=self.model_name,
                generation_config=generation_config,
            )
            self._is_available = True

        except ImportError:
            self._is_available = False
        except Exception:
            self._is_available = False

    def generate(self, prompt: str, system_prompt: str = "") -> dict[str, Any]:
        """Genera contenido con Gemini Pro (síncrono).

        Args:
            prompt: Texto del usuario.
            system_prompt: System prompt para el modelo.

        Returns:
            Dict con 'content' (texto generado) y 'metadata'.

        Raises:
            MissingAPIKeyError: Si API key no está configurada.
            RateLimitError: Si Gemini retorna 429.
            GeminiClientError: Para otros errores de API.
        """
        if not self._is_available:
            raise MissingAPIKeyError("GEMINI_API_KEY no está configurada o es inválida")

        try:
            contents = []
            if system_prompt:
                contents.append({"role": "user", "parts": [system_prompt + "\n\n" + prompt]})
            else:
                contents.append({"role": "user", "parts": [prompt]})

            response = self._model.generate_content(
                contents[0]["parts"],
                request_options={"timeout": REQUEST_TIMEOUT}
            )

            return {
                "content": response.text,
                "metadata": {
                    "model": self.model_name,
                    "finish_reason": str(getattr(response.candidates[0], 'finish_reason', 'STOP'))
                        if response.candidates else "UNKNOWN",
                }
            }

        except Exception as e:
            error_msg = str(e).lower()
            if "429" in error_msg or "resource exhausted" in error_msg:
                raise RateLimitError(retry_after=60)
            if "api key" in error_msg or "unauthorized" in error_msg or "403" in error_msg:
                raise MissingAPIKeyError(f"API key inválida: {e}")
            raise GeminiClientError(f"Error de generación: {e}")

    def stream_generate(self, prompt: str, system_prompt: str = "") -> Generator[str, None, None]:
        """Genera contenido con Gemini Pro en modo streaming.

        Args:
            prompt: Texto del usuario.
            system_prompt: System prompt para el modelo.

        Yields:
            Chunks de texto generados incrementalmente.

        Raises:
            MissingAPIKeyError: Si API key no está configurada.
            RateLimitError: Si Gemini retorna 429.
            GeminiClientError: Para otros errores de API.
        """
        if not self._is_available:
            raise MissingAPIKeyError("GEMINI_API_KEY no está configurada o es inválida")

        try:
            full_prompt = system_prompt + "\n\n" + prompt if system_prompt else prompt

            response = self._model.generate_content(
                full_prompt,
                stream=True,
                request_options={"timeout": REQUEST_TIMEOUT}
            )

            for chunk in response:
                if chunk.text:
                    yield chunk.text

        except Exception as e:
            error_msg = str(e).lower()
            if "429" in error_msg or "resource exhausted" in error_msg:
                raise RateLimitError(retry_after=60)
            if "api key" in error_msg or "unauthorized" in error_msg:
                raise MissingAPIKeyError(f"API key inválida: {e}")
            raise GeminiClientError(f"Error de streaming: {e}")
