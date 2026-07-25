"""SDDGenerator — Orquestador agéntico para generación de especificaciones SDD.

Coordina el flujo de generación: Gemini Pro → EARS Formatter → Output,
con manejo de ambigüedades (AMB-1) y fallback a Smart Engine (GAP-1).

Attributes:
    MIN_PROMPT_WORDS: Umbral mínimo de palabras para detectar prompts vagos.
"""

import os
from typing import Any, Generator

from src.sdd_generator.gemini_client import (
    GeminiClient,
    GeminiClientError,
    MissingAPIKeyError,
    RateLimitError,
)
from src.sdd_generator.ears_formatter import EarsFormatter
from src.sdd_generator.smart_engine import SmartEngine

MIN_PROMPT_WORDS = 5


class SDDGenerator:
    """Orquestador principal de generación SDD EARS.

    Gestiona el pipeline completo: detección de ambigüedad,
    generación con Gemini Pro o fallback, y validación EARS.

    Attributes:
        gemini: Cliente Gemini Pro.
        formatter: Validador de patrones EARS.
        smart_engine: Motor de fallback local.
    """

    def __init__(self, gemini_client: GeminiClient | None = None):
        """Inicializa el generador SDD.

        Args:
            gemini_client: Cliente Gemini inyectable (para testing).
                Si None, crea uno con env var GEMINI_API_KEY.
        """
        self.gemini = gemini_client or GeminiClient()
        self.formatter = EarsFormatter()
        self.smart_engine = SmartEngine()

    def generate(self, prompt: str) -> dict[str, Any]:
        """Genera una especificación SDD completa.

        Flujo:
        1. Detecta si el prompt es vago (< 5 palabras) → expande contexto.
        2. Intenta generar con Gemini Pro.
        3. Si falla (API key ausente o 429), usa Smart Engine fallback.
        4. Valida patrones EARS en el output.

        Args:
            prompt: Descripción del proyecto o URL de repositorio.

        Returns:
            Dict con:
                - content: Markdown SDD generado
                - metadata: Info del modelo y generación
                - fallback: None si usó Gemini, str con razón si usó fallback
                - is_ambiguous: True si se detectó prompt vago
        """
        is_ambiguous = self._is_ambiguous_prompt(prompt)
        system_prompt = self._build_system_prompt(prompt, is_ambiguous)

        # Intentar generación con Gemini Pro
        try:
            result = self.gemini.generate(
                prompt=prompt,
                system_prompt=system_prompt
            )
            content = result["content"]
            metadata = result.get("metadata", {})

            # Validar patrones EARS
            ears_patterns = self.formatter.validate(content)
            metadata["ears_patterns_found"] = len(ears_patterns)
            metadata["ears_patterns"] = [p.value for p in ears_patterns]

            return {
                "content": content,
                "metadata": metadata,
                "fallback": None,
                "is_ambiguous": is_ambiguous
            }

        except MissingAPIKeyError:
            return self._fallback_generate(prompt, is_ambiguous, reason="missing_key")

        except RateLimitError:
            return self._fallback_generate(prompt, is_ambiguous, reason="rate_limit_429")

        except GeminiClientError:
            return self._fallback_generate(prompt, is_ambiguous, reason="api_error")

    def stream_generate(self, prompt: str) -> Generator[str, None, None]:
        """Genera SDD en modo streaming (chunks incrementales).

        Args:
            prompt: Descripción del proyecto.

        Yields:
            Chunks de texto markdown.

        Note:
            Si Gemini no está disponible, genera el fallback completo
            como un solo chunk.
        """
        is_ambiguous = self._is_ambiguous_prompt(prompt)
        system_prompt = self._build_system_prompt(prompt, is_ambiguous)

        try:
            for chunk in self.gemini.stream_generate(
                prompt=prompt,
                system_prompt=system_prompt
            ):
                yield chunk

        except (MissingAPIKeyError, RateLimitError, GeminiClientError):
            # Fallback: generar template completo como un solo chunk
            result = self._fallback_generate(prompt, is_ambiguous, reason="streaming_fallback")
            yield result["content"]

    def _is_ambiguous_prompt(self, prompt: str) -> bool:
        """Detecta si un prompt es vago (< 5 palabras).

        Args:
            prompt: Texto del usuario.

        Returns:
            True si el prompt tiene menos de MIN_PROMPT_WORDS palabras.
        """
        words = prompt.strip().split()
        return len(words) < MIN_PROMPT_WORDS

    def _build_system_prompt(self, prompt: str, is_ambiguous: bool) -> str:
        """Construye el system prompt desde el template Jinja2.

        Args:
            prompt: Texto del usuario.
            is_ambiguous: Si el prompt fue detectado como vago.

        Returns:
            System prompt renderizado.
        """
        template_path = os.path.join(
            os.path.dirname(__file__), 'templates', 'sdd_prompt.j2'
        )

        try:
            from jinja2 import Template
            with open(template_path, 'r', encoding='utf-8') as f:
                template = Template(f.read())

            return template.render(
                prompt=prompt,
                project_name=self._extract_project_name(prompt),
                language="es",
                is_ambiguous=is_ambiguous
            )
        except (ImportError, FileNotFoundError):
            # Fallback sin Jinja2: system prompt inline
            return self._inline_system_prompt(prompt)

    def _extract_project_name(self, prompt: str) -> str:
        """Extrae un nombre de proyecto del prompt.

        Args:
            prompt: Texto del usuario.

        Returns:
            Nombre corto del proyecto (primeras 5 palabras o URL).
        """
        if prompt.startswith("http"):
            parts = prompt.rstrip("/").split("/")
            return parts[-1] if parts else "Proyecto"

        words = prompt.strip().split()
        return " ".join(words[:5]) if words else "Proyecto"

    def _inline_system_prompt(self, prompt: str) -> str:
        """System prompt inline como fallback si Jinja2 no está disponible."""
        return (
            "You are a Lead Requirements Engineer. Generate an SDD specification "
            "using EARS syntax (Ubiquitous, Event-Driven, State-Driven, Optional, "
            "Unwanted Behavior). Include a Mermaid.js architecture diagram, "
            "a Decision Matrix with [AMB]/[GAP] classifications, and a traceable "
            "task plan. Return ONLY Markdown without code fences. "
            f"Project: {prompt}"
        )

    def _fallback_generate(
        self, prompt: str, is_ambiguous: bool, reason: str
    ) -> dict[str, Any]:
        """Genera SDD usando Smart Engine local (fallback).

        Args:
            prompt: Texto del usuario.
            is_ambiguous: Si el prompt es vago.
            reason: Razón del fallback (missing_key, rate_limit_429, api_error).

        Returns:
            Dict con content, metadata, fallback reason.
        """
        content = self.smart_engine.generate(prompt, is_ambiguous=is_ambiguous)

        return {
            "content": content,
            "metadata": {
                "model": "smart_engine_local",
                "fallback_reason": reason,
            },
            "fallback": reason,
            "is_ambiguous": is_ambiguous
        }
