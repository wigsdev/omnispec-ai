"""UniversalAIRouter — Estrategia Multi-Proveedor con failover automático.

Administra la rotación entre proveedores de IA gratuitos en orden de prioridad:
1. Gemini (gemini-flash-lite-latest) via google-genai SDK — cuota free generosa
2. Groq Llama (llama-3.3-70b-versatile) via groq SDK — 30 req/min free
3. Groq Qwen (qwen/qwen3.6-27b) via groq SDK — free, reasoning model
4. Groq GPT-OSS (openai/gpt-oss-120b) via groq SDK — free backup
5. SmartEngine (fallback local Jinja2 < 50ms)

Si un proveedor retorna 429, error de auth, o no tiene API key,
conmuta al siguiente sin lanzar errores al usuario.
"""

import os
import re
import time
from abc import ABC, abstractmethod
from typing import Any

from src.sdd_generator.smart_engine import SmartEngine


class AIProvider(ABC):
    """Interfaz base para proveedores de IA."""

    name: str = "unknown"
    model: str = "unknown"

    @abstractmethod
    def is_available(self) -> bool:
        """Indica si el proveedor tiene API key configurada."""
        ...

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        """Genera contenido con el proveedor.

        Args:
            prompt: Texto del usuario.
            system_prompt: Instrucciones del sistema.

        Returns:
            Texto generado.

        Raises:
            ProviderError: Si el proveedor falla (429, auth, etc).
        """
        ...


class ProviderError(Exception):
    """Error genérico de proveedor (triggers failover)."""

    def __init__(self, provider: str, reason: str):
        self.provider = provider
        self.reason = reason
        super().__init__(f"[{provider}] {reason}")


class GeminiProvider(AIProvider):
    """Proveedor Google Gemini via google-genai SDK (free tier generoso)."""

    name = "Gemini"
    model = "gemini-flash-lite-latest"

    def __init__(self):
        self._api_key = os.environ.get("GEMINI_API_KEY", "")
        self._client = None
        if self._api_key:
            self._init_client()

    def _init_client(self) -> None:
        try:
            from google import genai
            self._client = genai.Client(api_key=self._api_key)
        except (ImportError, Exception):
            self._client = None

    def is_available(self) -> bool:
        return bool(self._api_key) and self._client is not None

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.is_available():
            raise ProviderError(self.name, "API key not configured")
        try:
            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            response = self._client.models.generate_content(
                model=self.model,
                contents=full_prompt,
            )
            return response.text
        except Exception as e:
            err = str(e).lower()
            if "429" in err or "exhausted" in err or "quota" in err:
                raise ProviderError(self.name, "Rate limit 429")
            if "401" in err or "403" in err or "auth" in err:
                raise ProviderError(self.name, "Authentication error")
            raise ProviderError(self.name, str(e))


class GroqLlamaProvider(AIProvider):
    """Proveedor Groq con Llama 3.3 70B (free, rápido)."""

    name = "Groq-Llama"
    model = "llama-3.3-70b-versatile"

    def __init__(self):
        self._api_key = os.environ.get("GROQ_API_KEY", "")
        self._client = None
        if self._api_key:
            self._init_client()

    def _init_client(self) -> None:
        try:
            from groq import Groq
            self._client = Groq(api_key=self._api_key)
        except (ImportError, Exception):
            self._client = None

    def is_available(self) -> bool:
        return bool(self._api_key) and self._client is not None

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.is_available():
            raise ProviderError(self.name, "API key not configured")
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=8192,
            )
            return response.choices[0].message.content
        except Exception as e:
            err = str(e).lower()
            if "429" in err or "rate" in err:
                raise ProviderError(self.name, "Rate limit 429")
            if "401" in err or "auth" in err:
                raise ProviderError(self.name, "Authentication error")
            raise ProviderError(self.name, str(e))


class GroqQwenProvider(AIProvider):
    """Proveedor Groq con Qwen 3.6 27B (free, reasoning model)."""

    name = "Groq-Qwen"
    model = "qwen/qwen3.6-27b"

    def __init__(self):
        self._api_key = os.environ.get("GROQ_API_KEY", "")
        self._client = None
        if self._api_key:
            self._init_client()

    def _init_client(self) -> None:
        try:
            from groq import Groq
            self._client = Groq(api_key=self._api_key)
        except (ImportError, Exception):
            self._client = None

    def is_available(self) -> bool:
        return bool(self._api_key) and self._client is not None

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.is_available():
            raise ProviderError(self.name, "API key not configured")
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=8192,
            )
            content = response.choices[0].message.content
            # Qwen incluye <think> tags — remover reasoning interno
            return self._strip_thinking(content)
        except Exception as e:
            err = str(e).lower()
            if "429" in err or "rate" in err:
                raise ProviderError(self.name, "Rate limit 429")
            if "401" in err or "auth" in err:
                raise ProviderError(self.name, "Authentication error")
            raise ProviderError(self.name, str(e))

    def _strip_thinking(self, text: str) -> str:
        """Remueve bloques <think>...</think> del output de Qwen."""
        cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        return cleaned.strip()


class GroqGPTOSSProvider(AIProvider):
    """Proveedor Groq con GPT-OSS 120B (free backup)."""

    name = "Groq-GPT-OSS"
    model = "openai/gpt-oss-120b"

    def __init__(self):
        self._api_key = os.environ.get("GROQ_API_KEY", "")
        self._client = None
        if self._api_key:
            self._init_client()

    def _init_client(self) -> None:
        try:
            from groq import Groq
            self._client = Groq(api_key=self._api_key)
        except (ImportError, Exception):
            self._client = None

    def is_available(self) -> bool:
        return bool(self._api_key) and self._client is not None

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.is_available():
            raise ProviderError(self.name, "API key not configured")
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=8192,
            )
            return response.choices[0].message.content
        except Exception as e:
            err = str(e).lower()
            if "429" in err or "rate" in err:
                raise ProviderError(self.name, "Rate limit 429")
            if "401" in err or "auth" in err:
                raise ProviderError(self.name, "Authentication error")
            raise ProviderError(self.name, str(e))


class SmartEngineProvider(AIProvider):
    """Proveedor fallback local (Jinja2 templates, < 50ms)."""

    name = "SmartEngine"
    model = "local-jinja2"

    def __init__(self):
        self._engine = SmartEngine()

    def is_available(self) -> bool:
        return True  # Siempre disponible

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        is_ambiguous = len(prompt.strip().split()) < 5
        return self._engine.generate(prompt, is_ambiguous=is_ambiguous)


class UniversalAIRouter:
    """Router multi-proveedor con failover automático.

    Itera proveedores gratuitos en orden de prioridad. Si uno falla,
    conmuta al siguiente sin exponer errores al usuario.

    Attributes:
        providers: Lista ordenada de proveedores configurados.
    """

    def __init__(self, providers: list[AIProvider] | None = None):
        """Inicializa el router con la cadena de proveedores.

        Args:
            providers: Lista custom de proveedores (para testing).
                Si None, usa la cadena por defecto (todos gratuitos).
        """
        if providers is not None:
            self.providers = providers
        else:
            self.providers = [
                GeminiProvider(),
                GroqLlamaProvider(),
                GroqQwenProvider(),
                GroqGPTOSSProvider(),
                SmartEngineProvider(),
            ]

    def generate(
        self, prompt: str, system_prompt: str = ""
    ) -> dict[str, Any]:
        """Genera contenido usando el primer proveedor disponible.

        Itera la cadena de proveedores. Si uno falla (429, auth, etc),
        conmuta al siguiente automáticamente.

        Args:
            prompt: Texto del usuario.
            system_prompt: Instrucciones del sistema.

        Returns:
            Dict con 'content', 'provider', 'model', 'latency_ms'.
        """
        errors: list[str] = []

        for provider in self.providers:
            if not provider.is_available():
                errors.append(f"{provider.name}: not available")
                continue

            start = time.perf_counter()
            try:
                content = provider.generate(prompt, system_prompt)
                latency_ms = round((time.perf_counter() - start) * 1000, 1)

                return {
                    "content": content,
                    "provider": provider.name,
                    "model": provider.model,
                    "latency_ms": latency_ms,
                    "fallback_chain": errors if errors else None,
                }

            except ProviderError as e:
                latency_ms = round((time.perf_counter() - start) * 1000, 1)
                errors.append(f"{e.provider}: {e.reason} ({latency_ms}ms)")
                continue

        # Nunca debería llegar aquí (SmartEngine siempre disponible)
        return {
            "content": "",
            "provider": "none",
            "model": "none",
            "latency_ms": 0,
            "fallback_chain": errors,
            "error": "All providers failed",
        }

    def get_available_providers(self) -> list[str]:
        """Retorna nombres de proveedores con API key configurada."""
        return [p.name for p in self.providers if p.is_available()]


# Backward compatibility aliases
GeminiProvider = GeminiProvider
GroqProvider = GroqLlamaProvider
OpenAIProvider = GroqGPTOSSProvider
AnthropicProvider = GroqQwenProvider
