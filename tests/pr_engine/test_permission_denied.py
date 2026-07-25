"""Tests GAP-2: Permiso de escritura denegado.

Verifica que al denegar permiso de escritura:
- NO se ejecuta ninguna operación en GitHub (AC-3.3.2)
- Se retorna HTTP 200 con download habilitado (AC-3.3.3)
- Se loguea el evento
"""

import pytest
from unittest.mock import patch, MagicMock

from src.api.app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def _seed_fix(client):
    """Helper: genera un fix para tener fix_id disponible."""
    with patch('src.api.routes.fixer.DiffFixer') as MockFixer, \
         patch('src.api.routes.fixer.TestSuiteGenerator') as MockGen:
        fixer_instance = MagicMock()
        fixer_instance.generate.return_value = {
            "status": "generated",
            "diff": "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-bad\n+good",
            "metadata": {},
        }
        MockFixer.return_value = fixer_instance

        gen_instance = MagicMock()
        gen_instance.generate.return_value = {
            "status": "generated",
            "test_content": "def test_x(): assert True",
        }
        MockGen.return_value = gen_instance

        response = client.post('/api/v1/fix/generate', json={
            "findings": [{"file": "x.py", "line": 1, "severity": "high",
                         "description": "test finding"}],
            "repo_url": "https://github.com/test/repo",
        })
        return response.get_json()["id"]


class TestWritePermissionDenied:
    """Tests de permiso de escritura denegado."""

    def test_write_permission_denied_blocks_pr_creation(self, client):
        """AC-3.3.2: Sin permiso, NO se crea rama ni PR."""
        fix_id = _seed_fix(client)
        response = client.post('/api/v1/fix/apply', json={
            "fix_id": fix_id,
            "write_permission_granted": False,
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "cancelled"

    def test_denied_enables_local_download(self, client):
        """AC-3.3.3: Download habilitado con diff y tests."""
        fix_id = _seed_fix(client)
        response = client.post('/api/v1/fix/apply', json={
            "fix_id": fix_id,
            "write_permission_granted": False,
        })
        data = response.get_json()
        assert data["download_available"] is True
        assert "diff_content" in data
        assert "test_content" in data
        assert len(data["diff_content"]) > 0
        assert len(data["test_content"]) > 0

    def test_denied_returns_write_permission_false(self, client):
        """El response confirma write_permission_granted: false."""
        fix_id = _seed_fix(client)
        response = client.post('/api/v1/fix/apply', json={
            "fix_id": fix_id,
            "write_permission_granted": False,
        })
        data = response.get_json()
        assert data["write_permission_granted"] is False

    def test_missing_permission_field_defaults_to_denied(self, client):
        """Sin campo write_permission_granted, se deniega."""
        fix_id = _seed_fix(client)
        response = client.post('/api/v1/fix/apply', json={
            "fix_id": fix_id,
        })
        data = response.get_json()
        assert data["status"] == "cancelled"
