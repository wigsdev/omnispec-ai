"""Tests para src/sdd_generator/gemini_client.py.

Valida el cliente Gemini Pro: inicialización, generación,
streaming, y manejo de errores (429, API key, etc.).
"""

import pytest
from unittest.mock import MagicMock, patch

from src.sdd_generator.gemini_client import (
    GeminiClient,
    MissingAPIKeyError,
    RateLimitError,
    GeminiClientError,
    DEFAULT_MODEL,
    REQUEST_TIMEOUT,
)


class TestGeminiClientInit:
    """Tests de inicialización del cliente."""

    def test_init_without_api_key_marks_unavailable(self):
        """Cliente sin API key no está disponible."""
        with patch.dict('os.environ', {'GEMINI_API_KEY': ''}, clear=False):
            client = GeminiClient(api_key="")
            assert client.is_available is False

    def test_init_with_api_key_but_no_sdk_marks_unavailable(self):
        """Cliente con API key pero sin SDK instalado no está disponible."""
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'}, clear=False):
            with patch('builtins.__import__', side_effect=ImportError("No module")):
                client = GeminiClient(api_key="test-key")
                assert client.is_available is False

    def test_model_name_default(self):
        """El modelo por defecto es gemini-1.5-flash."""
        client = GeminiClient(api_key="")
        assert client.model_name == DEFAULT_MODEL

    def test_model_name_custom(self):
        """Se puede configurar un modelo custom."""
        client = GeminiClient(api_key="", model="gemini-pro")
        assert client.model_name == "gemini-pro"


class TestGeminiClientGenerate:
    """Tests de generación síncrona."""

    def test_generate_raises_missing_key_when_unavailable(self):
        """generate() lanza MissingAPIKeyError si el cliente no está disponible."""
        client = GeminiClient(api_key="")
        with pytest.raises(MissingAPIKeyError):
            client.generate("test prompt")

    def test_generate_success_returns_content(self):
        """generate() retorna content y metadata en happy path."""
        client = GeminiClient(api_key="fake-key")
        client._is_available = True

        mock_candidate = MagicMock()
        mock_candidate.finish_reason = "STOP"
        mock_response = MagicMock()
        mock_response.text = "# SDD Generated"
        mock_response.candidates = [mock_candidate]

        client._model = MagicMock()
        client._model.generate_content.return_value = mock_response

        result = client.generate("Build a payment system")
        assert result["content"] == "# SDD Generated"
        assert "metadata" in result

    def test_generate_429_raises_rate_limit_error(self):
        """generate() lanza RateLimitError cuando Gemini retorna 429."""
        client = GeminiClient(api_key="fake-key")
        client._is_available = True
        client._model = MagicMock()
        client._model.generate_content.side_effect = Exception("429 Resource Exhausted")

        with pytest.raises(RateLimitError) as exc_info:
            client.generate("test")
        assert exc_info.value.retry_after == 60

    def test_generate_generic_error_raises_client_error(self):
        """generate() lanza GeminiClientError para errores genéricos."""
        client = GeminiClient(api_key="fake-key")
        client._is_available = True
        client._model = MagicMock()
        client._model.generate_content.side_effect = Exception("Network timeout")

        with pytest.raises(GeminiClientError):
            client.generate("test")


class TestGeminiClientStreaming:
    """Tests de generación en streaming."""

    def test_stream_raises_missing_key_when_unavailable(self):
        """stream_generate() lanza MissingAPIKeyError si no disponible."""
        client = GeminiClient(api_key="")
        with pytest.raises(MissingAPIKeyError):
            list(client.stream_generate("test prompt"))

    def test_stream_yields_chunks(self):
        """stream_generate() produce chunks de texto."""
        client = GeminiClient(api_key="fake-key")
        client._is_available = True

        chunk1 = MagicMock()
        chunk1.text = "# SDD"
        chunk2 = MagicMock()
        chunk2.text = "\n## Requirements"

        client._model = MagicMock()
        client._model.generate_content.return_value = [chunk1, chunk2]

        chunks = list(client.stream_generate("Build app"))
        assert chunks == ["# SDD", "\n## Requirements"]

    def test_stream_429_raises_rate_limit(self):
        """stream_generate() lanza RateLimitError en 429."""
        client = GeminiClient(api_key="fake-key")
        client._is_available = True
        client._model = MagicMock()
        client._model.generate_content.side_effect = Exception("Resource exhausted 429")

        with pytest.raises(RateLimitError):
            list(client.stream_generate("test"))


class TestGeminiClientTimeout:
    """Tests de configuración de timeout."""

    def test_request_timeout_is_27_seconds(self):
        """El timeout de request está configurado a 27s (bajo el límite de 29s de API GW)."""
        assert REQUEST_TIMEOUT == 27
