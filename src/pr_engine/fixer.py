"""DiffFixer — Generador de parches Unified Diff con AIRouter multi-proveedor.

Genera diffs de remediación de seguridad usando el AIRouter
con System Prompt Role-3 (Test Automation Engineer).
Valida formato y detecta diffs vacíos.
"""

from typing import Any

from src.sdd_generator.ai_router import UniversalAIRouter

ROLE_3_SYSTEM_PROMPT = """You are a Test Automation Engineer specialized in security patch generation.

Generate a unified diff patch that fixes the identified vulnerabilities.

Rules:
- Output ONLY the unified diff, no explanation, no markdown fences.
- Start with --- a/ and +++ b/ lines (standard unified diff format).
- Fix ONLY the identified vulnerability (minimal change principle).
- Include inline comments explaining the fix where helpful.

Format:
--- a/path/to/file.py
+++ b/path/to/file.py
@@ -line,count +line,count @@
 context line
-removed line
+added line
 context line
"""


class DiffFixer:
    """Generador de parches de seguridad en formato unified diff.

    Usa AIRouter multi-proveedor para generar diffs deterministas
    y validables con git apply.
    """

    def __init__(self, ai_router: UniversalAIRouter | None = None, gemini_client=None):
        """Inicializa el fixer.

        Args:
            ai_router: Router multi-proveedor inyectable (para testing).
            gemini_client: Legacy param (backward compat for tests).
        """
        if gemini_client is not None:
            # Backward compatibility: wrap legacy client
            from src.sdd_generator.ai_router import AIProvider, ProviderError, SmartEngineProvider
            from src.sdd_generator.gemini_client import (
                GeminiClient, MissingAPIKeyError, RateLimitError, GeminiClientError,
            )

            class LegacyProvider(AIProvider):
                name = "Gemini"
                model = "legacy"

                def __init__(self, client):
                    self._client = client

                def is_available(self):
                    return self._client.is_available

                def generate(self, prompt, system_prompt=""):
                    try:
                        result = self._client.generate(prompt=prompt, system_prompt=system_prompt)
                        return result["content"]
                    except (MissingAPIKeyError, RateLimitError, GeminiClientError) as e:
                        raise ProviderError("Gemini", str(e))

            self.router = UniversalAIRouter(providers=[
                LegacyProvider(gemini_client),
                SmartEngineProvider(),
            ])
        else:
            self.router = ai_router or UniversalAIRouter()

    def generate(self, findings: list[dict[str, Any]]) -> dict[str, Any]:
        """Genera un unified diff para remediar los hallazgos.

        Args:
            findings: Lista de hallazgos de seguridad a corregir.

        Returns:
            Dict con 'diff', 'status', 'provider', 'latency_ms'.
        """
        if not findings:
            return {"status": "no_fix_needed", "message": "No hay hallazgos para corregir"}

        prompt = self._build_prompt(findings)

        result = self.router.generate(
            prompt=prompt,
            system_prompt=ROLE_3_SYSTEM_PROMPT,
        )

        content = result["content"].strip()
        provider = result.get("provider", "unknown")
        latency_ms = result.get("latency_ms", 0)

        # SmartEngine no genera diffs reales
        if provider == "SmartEngine":
            return {
                "status": "error",
                "message": "No hay proveedores de IA disponibles para generar el fix",
                "diff": "",
                "provider": provider,
                "latency_ms": latency_ms,
            }

        # Validar que el diff no está vacío
        if not self._is_valid_diff(content):
            return {
                "status": "no_fix_needed",
                "message": "El modelo no generó un diff aplicable",
                "provider": provider,
                "latency_ms": latency_ms,
            }

        return {
            "status": "generated",
            "diff": content,
            "provider": provider,
            "latency_ms": latency_ms,
            "metadata": {"model": result.get("model", "unknown")},
        }

    def _build_prompt(self, findings: list[dict[str, Any]]) -> str:
        """Construye el prompt con los hallazgos a corregir."""
        lines = ["Fix the following security findings:\n"]
        for i, f in enumerate(findings, 1):
            lines.append(
                f"{i}. [{f.get('severity', 'unknown')}] "
                f"{f.get('description', 'Unknown finding')} "
                f"in {f.get('file', '?')}:{f.get('line', '?')}"
            )
        return "\n".join(lines)

    def _is_valid_diff(self, diff_text: str) -> bool:
        """Valida que el texto es un unified diff con contenido."""
        if not diff_text:
            return False
        has_additions = '+' in diff_text
        has_removals = '-' in diff_text
        has_header = '@@' in diff_text or '---' in diff_text
        return has_header and (has_additions or has_removals)
