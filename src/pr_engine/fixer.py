"""DiffFixer — Generador de parches Unified Diff con Gemini Pro Role-3.

Genera diffs de remediación de seguridad usando Gemini Pro
con temperature=0.2 para determinismo. Valida formato y
detecta diffs vacíos.
"""

from typing import Any

from src.sdd_generator.gemini_client import (
    GeminiClient,
    MissingAPIKeyError,
    RateLimitError,
    GeminiClientError,
)

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

    Usa Gemini Pro Role-3 con temperature=0.2 para generar
    diffs deterministas y validables con git apply.
    """

    def __init__(self, gemini_client: GeminiClient | None = None):
        """Inicializa el fixer.

        Args:
            gemini_client: Cliente Gemini inyectable (para testing).
        """
        self.gemini = gemini_client or GeminiClient()

    def generate(self, findings: list[dict[str, Any]]) -> dict[str, Any]:
        """Genera un unified diff para remediar los hallazgos.

        Args:
            findings: Lista de hallazgos de seguridad a corregir.

        Returns:
            Dict con 'diff' (texto del patch) y 'status'.
            Si no hay fix necesario: {'status': 'no_fix_needed'}.
        """
        if not findings:
            return {"status": "no_fix_needed", "message": "No hay hallazgos para corregir"}

        prompt = self._build_prompt(findings)

        try:
            result = self.gemini.generate(
                prompt=prompt,
                system_prompt=ROLE_3_SYSTEM_PROMPT,
            )
            diff_text = result["content"].strip()

            # Validar que el diff no está vacío
            if not self._is_valid_diff(diff_text):
                return {"status": "no_fix_needed", "message": "El modelo no generó un diff aplicable"}

            return {
                "status": "generated",
                "diff": diff_text,
                "metadata": result.get("metadata", {}),
            }

        except (MissingAPIKeyError, RateLimitError, GeminiClientError) as e:
            return {
                "status": "error",
                "message": f"Error generando fix: {e}",
                "diff": "",
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
        """Valida que el texto es un unified diff con contenido.

        Args:
            diff_text: Texto generado por Gemini.

        Returns:
            True si contiene marcadores de diff (+/-/@@).
        """
        if not diff_text:
            return False
        has_additions = '+' in diff_text
        has_removals = '-' in diff_text
        has_header = '@@' in diff_text or '---' in diff_text
        return has_header and (has_additions or has_removals)
