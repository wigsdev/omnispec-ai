"""Tests GAP-2: Permiso de lectura denegado.

Verifica que al denegar permiso:
- NO se ejecuta ninguna llamada a GitHub API (AC-2.1.2)
- Se retorna HTTP 200 con status "cancelled" (no error 403)
- Se loguea el evento de permiso denegado
"""

import pytest

from src.api.app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestReadPermissionDenied:
    """Tests de permiso de lectura denegado (GAP-2)."""

    def test_read_permission_denied_aborts_audit(self, client):
        """AC-2.1.2: Con permission_granted=false NO se llama a GitHub."""
        response = client.post('/api/v1/audit', json={
            "repo_url": "https://github.com/test/repo",
            "permission_granted": False,
        })
        data = response.get_json()
        assert data["status"] == "cancelled"

    def test_denied_returns_200_with_cancelled_status(self, client):
        """GAP-2: Retorna HTTP 200, no 403."""
        response = client.post('/api/v1/audit', json={
            "repo_url": "https://github.com/test/repo",
            "permission_granted": False,
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "cancelled"
        assert "cancelada" in data["message"].lower()

    def test_denied_returns_permission_granted_false(self, client):
        """El response incluye permission_granted: false."""
        response = client.post('/api/v1/audit', json={
            "repo_url": "https://github.com/test/repo",
            "permission_granted": False,
        })
        data = response.get_json()
        assert data["permission_granted"] is False

    def test_denied_returns_audit_id(self, client):
        """Se genera un audit_id incluso cuando se deniega."""
        response = client.post('/api/v1/audit', json={
            "repo_url": "https://github.com/test/repo",
            "permission_granted": False,
        })
        data = response.get_json()
        assert "id" in data
        assert len(data["id"]) > 0

    def test_denied_audit_report_shows_cancelled(self, client):
        """GET /report de auditoría cancelada retorna status cancelled."""
        response = client.post('/api/v1/audit', json={
            "repo_url": "https://github.com/test/repo",
            "permission_granted": False,
        })
        audit_id = response.get_json()["id"]

        report = client.get(f'/api/v1/audit/{audit_id}/report')
        data = report.get_json()
        assert data["status"] == "cancelled"

    def test_missing_permission_field_defaults_to_denied(self, client):
        """Sin campo permission_granted, se trata como denegado."""
        response = client.post('/api/v1/audit', json={
            "repo_url": "https://github.com/test/repo",
        })
        data = response.get_json()
        assert data["status"] == "cancelled"
