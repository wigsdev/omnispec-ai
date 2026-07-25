"""Tests para src/sdd_generator/generator.py.

Valida el orquestador SDDGenerator con AIRouter: generación,
fallback a Smart Engine, y detección de ambigüedades.
"""

import pytest
from unittest.mock import MagicMock

from src.sdd_generator.generator import SDDGenerator, MIN_PROMPT_WORDS
from src.sdd_generator.ai_router import (
    UniversalAIRouter, AIProvider, ProviderError, SmartEngineProvider,
)


class MockProvider(AIProvider):
    """Mock provider for testing."""
    name = "MockGemini"
    model = "mock-model"

    def __init__(self, response="# SDD\n\nWhen the user submits, the system shall respond.\nThe system shall validate inputs."):
        self._response = response

    def is_available(self):
        return True

    def generate(self, prompt, system_prompt=""):
        return self._response


class FailingProvider(AIProvider):
    """Provider that always fails."""
    name = "FailingProvider"
    model = "fail"

    def is_available(self):
        return True

    def generate(self, prompt, system_prompt=""):
        raise ProviderError(self.name, "Rate limit 429")


@pytest.fixture
def mock_router():
    """Fixture: router con mock provider exitoso."""
    return UniversalAIRouter(providers=[MockProvider()])


@pytest.fixture
def generator(mock_router):
    """Fixture: SDDGenerator con router mockeado."""
    return SDDGenerator(ai_router=mock_router)


class TestSDDGeneratorGenerate:
    """Tests de generación principal."""

    def test_generate_returns_content(self, generator):
        result = generator.generate("Build a payment processing system")
        assert "content" in result
        assert result["content"] is not None
        assert len(result["content"]) > 0

    def test_generate_returns_metadata(self, generator):
        result = generator.generate("Build a payment processing system")
        assert "metadata" in result

    def test_generate_returns_provider(self, generator):
        result = generator.generate("Build a payment processing system")
        assert result["provider"] == "MockGemini"

    def test_generate_returns_latency_ms(self, generator):
        result = generator.generate("Build a payment processing system")
        assert "latency_ms" in result
        assert result["latency_ms"] >= 0

    def test_generate_returns_no_fallback_on_success(self, generator):
        result = generator.generate("Build a payment processing system")
        assert result["fallback"] is None

    def test_generate_validates_ears_patterns(self, generator):
        result = generator.generate("Build a payment processing system")
        assert "ears_patterns_found" in result["metadata"]
        assert result["metadata"]["ears_patterns_found"] >= 1


class TestSDDGeneratorFallback:
    """Tests de fallback a Smart Engine."""

    def test_fallback_on_all_providers_failing(self):
        router = UniversalAIRouter(providers=[FailingProvider(), SmartEngineProvider()])
        gen = SDDGenerator(ai_router=router)
        result = gen.generate("Build a payment system for merchants")
        assert result["fallback"] == "all_providers_failed"
        assert "content" in result
        assert len(result["content"]) > 0

    def test_fallback_on_missing_api_key(self):
        """SmartEngine se activa cuando no hay proveedores disponibles."""
        router = UniversalAIRouter(providers=[SmartEngineProvider()])
        gen = SDDGenerator(ai_router=router)
        result = gen.generate("Build a payment system for merchants")
        assert result["provider"] == "SmartEngine"

    def test_fallback_on_rate_limit(self):
        router = UniversalAIRouter(providers=[FailingProvider(), SmartEngineProvider()])
        gen = SDDGenerator(ai_router=router)
        result = gen.generate("Build an e-commerce platform with payments")
        assert result["provider"] == "SmartEngine"

    def test_fallback_content_contains_ears_patterns(self):
        router = UniversalAIRouter(providers=[SmartEngineProvider()])
        gen = SDDGenerator(ai_router=router)
        result = gen.generate("Build a task management application")
        content = result["content"]
        assert "system shall" in content.lower()
        assert "REQ-" in content


class TestSDDGeneratorStreaming:
    """Tests de streaming."""

    def test_stream_generate_yields_chunks(self):
        router = UniversalAIRouter(providers=[MockProvider("# SDD\n## Reqs")])
        gen = SDDGenerator(ai_router=router)
        chunks = list(gen.stream_generate("Build a system"))
        assert len(chunks) >= 1
        assert "# SDD" in chunks[0]

    def test_stream_fallback_on_error(self):
        router = UniversalAIRouter(providers=[FailingProvider(), SmartEngineProvider()])
        gen = SDDGenerator(ai_router=router)
        chunks = list(gen.stream_generate("Build a system"))
        assert len(chunks) >= 1
        assert "system shall" in chunks[0].lower()


class TestSDDGeneratorMinPromptWords:
    """Tests del umbral MIN_PROMPT_WORDS."""

    def test_min_prompt_words_is_five(self):
        assert MIN_PROMPT_WORDS == 5
