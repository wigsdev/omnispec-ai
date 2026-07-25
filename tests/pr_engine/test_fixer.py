"""Tests para src/pr_engine/fixer.py — Generador de diffs."""

import pytest
from unittest.mock import MagicMock

from src.pr_engine.fixer import DiffFixer
from src.sdd_generator.gemini_client import (
    GeminiClient, MissingAPIKeyError, RateLimitError,
)


@pytest.fixture
def mock_client():
    client = MagicMock(spec=GeminiClient)
    client.is_available = True
    client.generate.return_value = {
        "content": "--- a/config.py\n+++ b/config.py\n@@ -1,3 +1,3 @@\n-password = 'secret'\n+password = os.environ['DB_PASSWORD']\n",
        "metadata": {"model": "gemini-1.5-flash"},
    }
    return client


@pytest.fixture
def fixer(mock_client):
    return DiffFixer(gemini_client=mock_client)


class TestDiffGeneration:
    """Tests de generación de diff."""

    def test_generate_returns_valid_diff(self, fixer):
        findings = [{"file": "config.py", "line": 1, "severity": "critical",
                     "description": "Password hardcoded"}]
        result = fixer.generate(findings)
        assert result["status"] == "generated"
        assert "---" in result["diff"]
        assert "+++" in result["diff"]

    def test_generate_no_findings_returns_no_fix_needed(self, fixer):
        result = fixer.generate([])
        assert result["status"] == "no_fix_needed"

    def test_generate_empty_diff_returns_no_fix_needed(self):
        client = MagicMock(spec=GeminiClient)
        client.generate.return_value = {"content": "", "metadata": {}}
        f = DiffFixer(gemini_client=client)
        findings = [{"file": "x.py", "line": 1, "severity": "high",
                     "description": "test"}]
        result = f.generate(findings)
        assert result["status"] == "no_fix_needed"

    def test_gemini_429_during_fix_generation(self):
        """4.13: Gemini 429 retorna error informativo."""
        client = MagicMock(spec=GeminiClient)
        client.generate.side_effect = RateLimitError(retry_after=60)
        f = DiffFixer(gemini_client=client)
        findings = [{"file": "x.py", "line": 1, "severity": "high",
                     "description": "test"}]
        result = f.generate(findings)
        assert result["status"] == "error"
        assert "429" in result["message"] or "Rate limit" in result["message"]

    def test_missing_api_key_returns_error(self):
        client = MagicMock(spec=GeminiClient)
        client.generate.side_effect = MissingAPIKeyError("No key")
        f = DiffFixer(gemini_client=client)
        findings = [{"file": "x.py", "line": 1, "severity": "high",
                     "description": "test"}]
        result = f.generate(findings)
        assert result["status"] == "error"

    def test_invalid_diff_detected(self):
        """4.18: Diff sin marcadores no es válido."""
        client = MagicMock(spec=GeminiClient)
        client.generate.return_value = {"content": "no diff here just text", "metadata": {}}
        f = DiffFixer(gemini_client=client)
        findings = [{"file": "x.py", "line": 1, "severity": "high",
                     "description": "test"}]
        result = f.generate(findings)
        assert result["status"] == "no_fix_needed"
