"""Tests para src/sdd_generator/generator.py.

Valida el orquestador SDDGenerator: generación con Gemini,
fallback a Smart Engine, y detección de ambigüedades.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.sdd_generator.generator import SDDGenerator, MIN_PROMPT_WORDS
from src.sdd_generator.gemini_client import (
    GeminiClient,
    MissingAPIKeyError,
    RateLimitError,
    GeminiClientError,
)


@pytest.fixture
def mock_gemini_client():
    """Fixture: cliente Gemini mockeado con respuesta exitosa."""
    client = MagicMock(spec=GeminiClient)
    client.is_available = True
    client.generate.return_value = {
        "content": "# SDD\n\nWhen the user submits, the system shall respond.\nThe system shall validate inputs.",
        "metadata": {"model": "gemini-1.5-flash", "finish_reason": "STOP"}
    }
    return client


@pytest.fixture
def generator(mock_gemini_client):
    """Fixture: SDDGenerator con cliente Gemini mockeado."""
    return SDDGenerator(gemini_client=mock_gemini_client)


class TestSDDGeneratorGenerate:
    """Tests de generación principal."""

    def test_generate_returns_content(self, generator):
        """generate() retorna content markdown."""
        result = generator.generate("Build a payment processing system")
        assert "content" in result
        assert result["content"] is not None
        assert len(result["content"]) > 0

    def test_generate_returns_metadata(self, generator):
        """generate() retorna metadata del modelo."""
        result = generator.generate("Build a payment processing system")
        assert "metadata" in result
        assert result["metadata"]["model"] == "gemini-1.5-flash"

    def test_generate_returns_no_fallback_on_success(self, generator):
        """generate() retorna fallback=None cuando Gemini responde OK."""
        result = generator.generate("Build a payment processing system")
        assert result["fallback"] is None

    def test_generate_validates_ears_patterns(self, generator):
        """generate() valida patrones EARS en el output."""
        result = generator.generate("Build a payment processing system")
        assert "ears_patterns_found" in result["metadata"]
        assert result["metadata"]["ears_patterns_found"] >= 1

    def test_generate_calls_gemini_with_prompt(self, generator, mock_gemini_client):
        """generate() invoca Gemini con el prompt del usuario."""
        generator.generate("Build a chat application")
        mock_gemini_client.generate.assert_called_once()
        call_kwargs = mock_gemini_client.generate.call_args
        assert "Build a chat application" in call_kwargs.kwargs["prompt"]


class TestSDDGeneratorFallback:
    """Tests de fallback a Smart Engine."""

    def test_fallback_on_missing_api_key(self):
        """Usa Smart Engine cuando API key está ausente."""
        client = MagicMock(spec=GeminiClient)
        client.generate.side_effect = MissingAPIKeyError("No key")
        gen = SDDGenerator(gemini_client=client)

        result = gen.generate("Build a payment system for merchants")
        assert result["fallback"] == "missing_key"
        assert "content" in result
        assert len(result["content"]) > 0

    def test_fallback_on_rate_limit(self):
        """Usa Smart Engine cuando Gemini retorna 429."""
        client = MagicMock(spec=GeminiClient)
        client.generate.side_effect = RateLimitError(retry_after=60)
        gen = SDDGenerator(gemini_client=client)

        result = gen.generate("Build an e-commerce platform with payments")
        assert result["fallback"] == "rate_limit_429"
        assert "content" in result

    def test_fallback_on_api_error(self):
        """Usa Smart Engine cuando Gemini retorna error genérico."""
        client = MagicMock(spec=GeminiClient)
        client.generate.side_effect = GeminiClientError("Network error")
        gen = SDDGenerator(gemini_client=client)

        result = gen.generate("Build a healthcare monitoring dashboard")
        assert result["fallback"] == "api_error"

    def test_fallback_content_contains_ears_patterns(self):
        """El contenido de fallback contiene patrones EARS válidos."""
        client = MagicMock(spec=GeminiClient)
        client.generate.side_effect = MissingAPIKeyError("No key")
        gen = SDDGenerator(gemini_client=client)

        result = gen.generate("Build a task management application")
        content = result["content"]
        assert "the system shall" in content.lower()
        assert "REQ-" in content


class TestSDDGeneratorStreaming:
    """Tests de streaming."""

    def test_stream_generate_yields_chunks(self, mock_gemini_client):
        """stream_generate() produce chunks de texto."""
        mock_gemini_client.stream_generate.return_value = iter(["# SDD", "\n## Reqs"])
        gen = SDDGenerator(gemini_client=mock_gemini_client)

        chunks = list(gen.stream_generate("Build a system"))
        assert len(chunks) == 2
        assert chunks[0] == "# SDD"

    def test_stream_fallback_on_error(self):
        """stream_generate() produce fallback como un chunk si Gemini falla."""
        client = MagicMock(spec=GeminiClient)
        client.stream_generate.side_effect = MissingAPIKeyError("No key")
        gen = SDDGenerator(gemini_client=client)

        chunks = list(gen.stream_generate("Build a system"))
        assert len(chunks) == 1
        assert "system shall" in chunks[0].lower()


class TestSDDGeneratorMinPromptWords:
    """Tests del umbral MIN_PROMPT_WORDS."""

    def test_min_prompt_words_is_five(self):
        """El umbral de palabras mínimas es 5."""
        assert MIN_PROMPT_WORDS == 5
