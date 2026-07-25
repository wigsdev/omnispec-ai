"""Tests de fallback Smart Engine (GAP-1).

Verifica que el Smart Engine responde en < 50 ms cuando:
- Todos los proveedores cloud fallan.
- Solo SmartEngine está disponible.
"""

import time

import pytest

from src.sdd_generator.generator import SDDGenerator
from src.sdd_generator.ai_router import (
    UniversalAIRouter, AIProvider, ProviderError, SmartEngineProvider,
)
from src.sdd_generator.smart_engine import SmartEngine


class FailingProvider(AIProvider):
    """Provider that simulates 429."""
    name = "FailCloud"
    model = "fail"

    def is_available(self):
        return True

    def generate(self, prompt, system_prompt=""):
        raise ProviderError(self.name, "Rate limit 429")


@pytest.fixture
def smart_engine():
    return SmartEngine()


class TestSmartEnginePerformance:
    """Tests de latencia del Smart Engine (< 50 ms)."""

    def test_missing_api_key_activates_smart_engine_under_50ms(self):
        """AC-GAP-1.1: Sin proveedores cloud, fallback en < 50 ms."""
        router = UniversalAIRouter(providers=[SmartEngineProvider()])
        gen = SDDGenerator(ai_router=router)

        start = time.perf_counter()
        result = gen.generate("Build a complete payment system")
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 50, f"Fallback took {elapsed_ms:.1f}ms (> 50ms)"
        assert result["provider"] == "SmartEngine"

    def test_rate_limit_429_uses_smart_engine_under_50ms(self):
        """AC-GAP-1.2: Con 429, fallback responde en < 50 ms."""
        router = UniversalAIRouter(providers=[FailingProvider(), SmartEngineProvider()])
        gen = SDDGenerator(ai_router=router)

        start = time.perf_counter()
        result = gen.generate("Build an inventory management system")
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 50, f"Fallback took {elapsed_ms:.1f}ms (> 50ms)"
        assert result["provider"] == "SmartEngine"


class TestSmartEngineContent:
    """Tests del contenido generado por Smart Engine."""

    def test_generates_ears_requirements(self, smart_engine):
        content = smart_engine.generate("Build a system")
        assert "system shall" in content.lower()
        assert "REQ-" in content

    def test_generates_mermaid_diagram(self, smart_engine):
        content = smart_engine.generate("Build a system")
        assert "```mermaid" in content
        assert "graph" in content

    def test_generates_decision_matrix(self, smart_engine):
        content = smart_engine.generate("Build a system")
        assert "[AMB]" in content or "[GAP]" in content

    def test_generates_task_plan(self, smart_engine):
        content = smart_engine.generate("Build a system")
        assert "- [ ]" in content
        assert "Refs:" in content

    def test_amb_section_included_for_vague_prompt(self, smart_engine):
        content = smart_engine.generate("pagos", is_ambiguous=True)
        assert "[AMB] Contexto Inferido" in content

    def test_no_amb_section_for_normal_prompt(self, smart_engine):
        content = smart_engine.generate("Build a complete system", is_ambiguous=False)
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
    def test_infers_domain_from_keywords(self, smart_engine, prompt, expected_domain):
        content = smart_engine.generate(prompt, is_ambiguous=True)
        assert expected_domain in content.lower()

    def test_default_domain_for_unknown_keywords(self, smart_engine):
        content = smart_engine.generate("xyz", is_ambiguous=True)
        assert "saas" in content.lower() or "genérico" in content.lower()
