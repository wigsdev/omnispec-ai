"""Tests de la interfaz web base (Tarea 1).

Verifica que el servidor Flask sirve correctamente el HTML
con las 3 pestañas y el endpoint de health.
"""

import pytest

from src.api.app import create_app


@pytest.fixture
def client():
    """Fixture: cliente de test Flask."""
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestIndexRoute:
    """Tests para GET / — Interfaz gráfica principal."""

    def test_index_returns_200(self, client):
        """GET / debe retornar HTTP 200."""
        response = client.get('/')
        assert response.status_code == 200

    def test_index_returns_html(self, client):
        """GET / debe retornar content-type HTML."""
        response = client.get('/')
        assert 'text/html' in response.content_type

    def test_index_contains_three_tabs(self, client):
        """GET / debe contener las 3 pestañas principales."""
        response = client.get('/')
        html = response.data.decode('utf-8')
        assert 'SDD Generator' in html
        assert 'Auditor 3D' in html
        assert 'Auto-Fix Engine' in html

    def test_index_contains_tab_panels(self, client):
        """GET / debe contener los 3 paneles de contenido."""
        response = client.get('/')
        html = response.data.decode('utf-8')
        assert 'panel-generator' in html
        assert 'panel-auditor' in html
        assert 'panel-fixer' in html

    def test_index_loads_marked_js_cdn(self, client):
        """GET / debe incluir marked.js desde CDN."""
        response = client.get('/')
        html = response.data.decode('utf-8')
        assert 'marked' in html

    def test_index_loads_mermaid_js_cdn(self, client):
        """GET / debe incluir mermaid.js desde CDN."""
        response = client.get('/')
        html = response.data.decode('utf-8')
        assert 'mermaid' in html


class TestHealthEndpoint:
    """Tests para GET /api/v1/health."""

    def test_health_returns_200(self, client):
        """GET /api/v1/health debe retornar HTTP 200."""
        response = client.get('/api/v1/health')
        assert response.status_code == 200

    def test_health_returns_json(self, client):
        """GET /api/v1/health debe retornar JSON."""
        response = client.get('/api/v1/health')
        assert response.content_type == 'application/json'

    def test_health_returns_ok_status(self, client):
        """GET /api/v1/health debe retornar {status: ok}."""
        response = client.get('/api/v1/health')
        data = response.get_json()
        assert data == {"status": "ok"}
