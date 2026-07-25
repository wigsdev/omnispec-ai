"""Tests de fallback Smart Engine (GAP-1).

Verifica que el Smart Engine responde en < 50 ms cuando:
- GEMINI_API_KEY está ausente.
- Gemini Pro retorna 429 Rate Limit.
- Cache DynamoDB miss (solo template Jinja2).
"""

import time

import pytest
from unittest.mock import MagicMock

from src.sdd_generator.generator import SDDGenerator
from src.sdd_generator.gemini_client import (
    GeminiClient,
    MissingAPIKeyError,
    RateLimitError,
)
from src.sdd_generator.smart_engine import SmartEngine


@pytest.fixture
def smart_engine():
    """Fixture: instancia de SmartEngine."""
    return SmartEngine()


class TestSmartEnginePerformance:
    """Tests de latencia del Smart Engine (< 50 ms)."""

    def test_missing_api_key_activates_smart_engine_under_50ms(self):
        """AC-GAP-1.1: Sin API key, fallback responde en < 50 ms."""
        client = MagicMock(spec=GeminiClient)
        client.generate.side_effect = MissingAPIKeyError("No key")
        gen = SDDGenerator(gemini_client=client)

        start = time.perf_counter()
        result = gen.generate("Build a complete payment system")
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 50, f"Fallback took {elapsed_ms:.1f}ms (> 50ms)"
        assert result["fallback"] == "missing_key"

    def test_rate_limit_429_uses_smart_engine_under_50ms(self):
        """AC-GAP-1.2: Con 429, fallback responde en < 50 ms."""
        client = MagicMock(spec=GeminiClient)
        client.generate.side_effect = RateLimitError(retry_after=60)
        gen = SDDGenerator(gemini_client=client)

        start = time.perf_counter()
        result = gen.generate("Build an inventory management system")
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 50, f"Fallback took {elapsed_ms:.1f}ms (> 50ms)"
        assert result["fallback"] == "rate_limit_429"


class TestSmartEngineContent:
    """Tests del contenido generado por Smart Engine."""

    def test_generates_ears_requirements(self, smart_engine):
        """El output contiene requisitos EARS válidos."""
        content = smart_engine.generate("Build a system")
        assert "system shall" in content.lower()
        assert "REQ-" in content

    def test_generates_mermaid_diagram(self, smart_engine):
        """El output contiene diagrama Mermaid."""
        content = smart_engine.generate("Build a system")
        assert "```mermaid" in content
        assert "graph" in content

    def test_generates_decision_matrix(self, smart_engine):
        """El output contiene matriz de decisiones."""
        content = smart_engine.generate("Build a system")
        assert "[AMB]" in content or "[GAP]" in content

    def test_generates_task_plan(self, smart_engine):
        """El output contiene plan de tareas."""
        content = smart_engine.generate("Build a system")
        assert "- [ ]" in content
        assert "Refs:" in content

    def test_amb_section_included_for_vague_prompt(self, smart_engine):
        """Prompts vagos incluyen sección [AMB]."""
        content = smart_engine.generate("pagos", is_ambiguous=True)
        assert "[AMB] Contexto Inferido" in content

    def test_no_amb_section_for_normal_prompt(self, smart_engine):
        """Prompts normales NO incluyen sección [AMB]."""
        content = smart_engine.generate(
            "Build a complete system", is_ambiguous=False
        )
        assert "[AMB] Contexto Inferido" not in content


class TestSmartEngineDomainInference:
    """Tests de inferencia de dominio."""

    @pytest.mark.parametrize("prompt,expected_domain", [
        ("pagos", "fintech"),
        ("tienda", "e-commerce"),
        ("salud", "healthcare"),
        ("chat", "comunicaciones"),
        ("sensor", "iot"),
    ])
    def test_infers_domain_from_keywords(
        self, smart_engine, prompt, expected_domain
    ):
        """Infiere dominio correcto desde keywords."""
        content = smart_engine.generate(prompt, is_ambiguous=True)
        assert expected_domain in content.lower()

    def test_default_domain_for_unknown_keywords(self, smart_engine):
        """Usa 'SaaS genérico' para keywords desconocidos."""
        content = smart_engine.generate("xyz", is_ambiguous=True)
        assert "saas" in content.lower() or "genérico" in content.lower()
