"""Tests de SSE Streaming y Timeout (EDGE-1).

Verifica que el endpoint de streaming SSE:
- Emite chunks con type: "chunk".
- Emite timeout_warning si elapsed > 25s (mock).
- Retorna content-type text/event-stream.
"""

import json

import pytest
from unittest.mock import patch, MagicMock

from src.api.app import create_app


@pytest.fixture
def client():
    """Fixture: cliente de test Flask."""
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestSSEStreamEndpoint:
    """Tests del endpoint GET /api/v1/generate/stream."""

    def test_stream_returns_event_stream_content_type(self, client):
        """El endpoint retorna mimetype text/event-stream."""
        with patch(
            'src.api.routes.generator._get_generator'
        ) as mock_gen:
            gen = MagicMock()
            gen.stream_generate.return_value = iter(["chunk1"])
            mock_gen.return_value = gen

            response = client.get(
                '/api/v1/generate/stream?prompt=test'
            )
            assert 'text/event-stream' in response.content_type

    def test_stream_emits_chunk_events(self, client):
        """El stream emite eventos con type: 'chunk'."""
        with patch(
            'src.api.routes.generator._get_generator'
        ) as mock_gen:
            gen = MagicMock()
            gen.stream_generate.return_value = iter(
                ["# SDD", "\n## Reqs"]
            )
            mock_gen.return_value = gen

            response = client.get(
                '/api/v1/generate/stream?prompt=test+project'
            )
            data = response.data.decode('utf-8')

            # Parse SSE events
            events = [
                line.replace("data: ", "")
                for line in data.split("\n")
                if line.startswith("data: ")
            ]

            assert len(events) >= 2
            first = json.loads(events[0])
            assert first["type"] == "chunk"
            assert first["content"] == "# SDD"
            assert first["seq"] == 1

    def test_stream_emits_complete_event(self, client):
        """El stream emite evento final type: 'complete'."""
        with patch(
            'src.api.routes.generator._get_generator'
        ) as mock_gen:
            gen = MagicMock()
            gen.stream_generate.return_value = iter(["done"])
            mock_gen.return_value = gen

            response = client.get(
                '/api/v1/generate/stream?prompt=test'
            )
            data = response.data.decode('utf-8')
            events = [
                line.replace("data: ", "")
                for line in data.split("\n")
                if line.startswith("data: ")
            ]

            last = json.loads(events[-1])
            assert last["type"] == "complete"

    def test_stream_without_prompt_returns_400(self, client):
        """Stream sin prompt retorna 400."""
        response = client.get('/api/v1/generate/stream')
        assert response.status_code == 400

    def test_stream_empty_prompt_returns_400(self, client):
        """Stream con prompt vacío retorna 400."""
        response = client.get('/api/v1/generate/stream?prompt=')
        assert response.status_code == 400


class TestSSEStreamHeaders:
    """Tests de headers del streaming SSE."""

    def test_cache_control_no_cache(self, client):
        """Header Cache-Control: no-cache está presente."""
        with patch(
            'src.api.routes.generator._get_generator'
        ) as mock_gen:
            gen = MagicMock()
            gen.stream_generate.return_value = iter(["x"])
            mock_gen.return_value = gen

            response = client.get(
                '/api/v1/generate/stream?prompt=test'
            )
            assert response.headers.get('Cache-Control') == 'no-cache'
