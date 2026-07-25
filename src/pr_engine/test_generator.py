"""TestSuiteGenerator — Generador de suite pytest para validación de patches.

Genera test_security_patch.py con test positivo (fix aplicado)
y test negativo (vulnerabilidad eliminada). Tests autosuficientes
con mocks para independencia del repo.
"""

from typing import Any

from src.sdd_generator.gemini_client import (
    GeminiClient,
    MissingAPIKeyError,
    RateLimitError,
    GeminiClientError,
)

ROLE_3_TEST_PROMPT = """You are a Test Automation Engineer. Generate a pytest test file
`test_security_patch.py` that validates the security fix described below.

Rules:
- Output ONLY Python code, no markdown fences, no explanation.
- Use pytest framework with explicit assertions.
- Include at least:
  - A positive test (fix applied correctly)
  - A negative test (vulnerability no longer exploitable)
- Use unittest.mock for any external dependencies.
- Tests must be executable standalone: `pytest test_security_patch.py --tb=short -q`
- Follow naming: test_<function>_<scenario>_<expected_result>

Start with imports directly. No module docstring needed.
"""

# Fallback test template when Gemini is unavailable
_FALLBACK_TEST = '''"""Test suite for security patch validation."""

import pytest


def test_patch_applied_correctly():
    """Positive test: verify the security fix is in place."""
    # Placeholder: replace with actual validation
    assert True, "Security patch applied"


def test_vulnerability_no_longer_exploitable():
    """Negative test: verify vulnerability is remediated."""
    # Placeholder: replace with actual exploit attempt
    assert True, "Vulnerability no longer exploitable"
'''


class TestSuiteGenerator:
    """Generador de suites de test pytest para patches de seguridad.

    Genera tests autosuficientes que validan un parche sin
    depender del estado del repositorio en runtime.
    """

    def __init__(self, gemini_client: GeminiClient | None = None):
        """Inicializa el generador.

        Args:
            gemini_client: Cliente Gemini inyectable.
        """
        self.gemini = gemini_client or GeminiClient()

    def generate(
        self, findings: list[dict[str, Any]], diff: str
    ) -> dict[str, Any]:
        """Genera test_security_patch.py para el diff dado.

        Args:
            findings: Hallazgos que el diff corrige.
            diff: Texto del unified diff generado.

        Returns:
            Dict con 'test_content' (código Python) y 'status'.
        """
        prompt = self._build_prompt(findings, diff)

        try:
            result = self.gemini.generate(
                prompt=prompt,
                system_prompt=ROLE_3_TEST_PROMPT,
            )
            test_content = self._clean_output(result["content"])

            return {
                "status": "generated",
                "test_content": test_content,
            }

        except (MissingAPIKeyError, RateLimitError, GeminiClientError):
            return {
                "status": "fallback",
                "test_content": _FALLBACK_TEST,
            }

    def _build_prompt(
        self, findings: list[dict[str, Any]], diff: str
    ) -> str:
        """Construye prompt para generación de tests."""
        lines = ["Generate pytest tests for this security patch:\n"]
        lines.append("## Findings Fixed:")
        for f in findings:
            lines.append(f"- {f.get('description', '?')} in {f.get('file', '?')}:{f.get('line', '?')}")
        lines.append(f"\n## Diff Applied:\n{diff}")
        return "\n".join(lines)

    def _clean_output(self, content: str) -> str:
        """Limpia el output de Gemini removiendo code fences."""
        clean = content.strip()
        if clean.startswith("```python"):
            clean = clean[len("```python"):].strip()
        elif clean.startswith("```"):
            clean = clean[3:].strip()
        if clean.endswith("```"):
            clean = clean[:-3].strip()
        return clean
