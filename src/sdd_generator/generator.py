"""SDDGenerator — Orquestador agéntico para generación de especificaciones SDD.

Coordina el flujo de generación: AIRouter → EARS Formatter → Output,
con manejo de ambigüedades (AMB-1) y failover multi-proveedor.

Attributes:
    MIN_PROMPT_WORDS: Umbral mínimo de palabras para detectar prompts vagos.
"""

import os
from typing import Any, Generator

from src.sdd_generator.ai_router import UniversalAIRouter, ProviderError
from src.sdd_generator.ears_formatter import EarsFormatter
from src.sdd_generator.smart_engine import SmartEngine

MIN_PROMPT_WORDS = 5


class SDDGenerator:
    """Orquestador principal de generación SDD EARS.

    Gestiona el pipeline completo: detección de ambigüedad,
    generación con AIRouter multi-proveedor, y validación EARS.

    Attributes:
        router: Router multi-proveedor de IA.
        formatter: Validador de patrones EARS.
        smart_engine: Motor de fallback local.
    """

    def __init__(self, ai_router: UniversalAIRouter | None = None):
        """Inicializa el generador SDD.

        Args:
            ai_router: Router multi-proveedor inyectable (para testing).
                Si None, crea uno con proveedores por defecto.
        """
        self.router = ai_router or UniversalAIRouter()
        self.formatter = EarsFormatter()
        self.smart_engine = SmartEngine()

    def generate(self, prompt: str) -> dict[str, Any]:
        """Genera una especificación SDD completa.

        Flujo:
        1. Detecta si el prompt es vago (< 5 palabras) → expande contexto.
        2. Invoca AIRouter (failover automático entre proveedores).
        3. Valida patrones EARS en el output.

        Args:
            prompt: Descripción del proyecto o URL de repositorio.

        Returns:
            Dict con:
                - content: Markdown SDD generado
                - metadata: Info del modelo y generación
                - provider: Nombre del proveedor que respondió
                - latency_ms: Tiempo de respuesta
                - fallback: None si usó IA, str con razón si usó fallback
                - is_ambiguous: True si se detectó prompt vago
        """
        is_ambiguous = self._is_ambiguous_prompt(prompt)
        system_prompt = self._build_system_prompt(prompt, is_ambiguous)

        result = self.router.generate(prompt=prompt, system_prompt=system_prompt)

        content = result["content"]
        provider = result.get("provider", "unknown")
        latency_ms = result.get("latency_ms", 0)

        # Validar patrones EARS
        ears_patterns = self.formatter.validate(content)

        metadata = {
            "model": result.get("model", "unknown"),
            "ears_patterns_found": len(ears_patterns),
            "ears_patterns": [p.value for p in ears_patterns],
            "fallback_chain": result.get("fallback_chain"),
        }

        is_fallback = provider == "SmartEngine"

        return {
            "content": content,
            "metadata": metadata,
            "provider": provider,
            "latency_ms": latency_ms,
            "fallback": "all_providers_failed" if is_fallback else None,
            "is_ambiguous": is_ambiguous,
        }

    def stream_generate(self, prompt: str) -> Generator[str, None, None]:
        """Genera SDD en modo streaming (chunks incrementales).

        Note: Streaming usa el router síncronamente y retorna
        el contenido completo como un solo chunk (los proveedores
        no todos soportan streaming nativo).

        Args:
            prompt: Descripción del proyecto.

        Yields:
            Chunks de texto markdown.
        """
        is_ambiguous = self._is_ambiguous_prompt(prompt)
        system_prompt = self._build_system_prompt(prompt, is_ambiguous)

        result = self.router.generate(prompt=prompt, system_prompt=system_prompt)
        yield result["content"]

    def _is_ambiguous_prompt(self, prompt: str) -> bool:
        """Detecta si un prompt es vago (< 5 palabras)."""
        words = prompt.strip().split()
        return len(words) < MIN_PROMPT_WORDS

    def _build_system_prompt(self, prompt: str, is_ambiguous: bool) -> str:
        """Construye el system prompt desde el template Jinja2."""
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
            return self._inline_system_prompt(prompt)

    def _extract_project_name(self, prompt: str) -> str:
        """Extrae un nombre de proyecto del prompt."""
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
