"""Tests para src/pr_engine/test_generator.py — Generador de tests."""

import pytest
from unittest.mock import MagicMock

from src.pr_engine.test_generator import TestSuiteGenerator, _FALLBACK_TEST
from src.sdd_generator.gemini_client import (
    GeminiClient, MissingAPIKeyError, RateLimitError,
)


@pytest.fixture
def mock_client():
    client = MagicMock(spec=GeminiClient)
    client.generate.return_value = {
        "content": "import pytest\n\ndef test_fix_applied():\n    assert True\n\ndef test_vuln_gone():\n    assert True\n",
        "metadata": {},
    }
    return client


@pytest.fixture
def gen(mock_client):
    return TestSuiteGenerator(gemini_client=mock_client)


class TestSuiteGeneration:
    """Tests del generador de suites pytest."""

    def test_generates_test_content(self, gen):
        findings = [{"file": "x.py", "line": 1, "description": "test"}]
        result = gen.generate(findings, "--- a/x.py\n+++ b/x.py\n")
        assert result["status"] == "generated"
        assert "def test_" in result["test_content"]

    def test_removes_code_fences(self):
        client = MagicMock(spec=GeminiClient)
        client.generate.return_value = {
            "content": "```python\nimport pytest\ndef test_x(): pass\n```",
            "metadata": {},
        }
        gen = TestSuiteGenerator(gemini_client=client)
        result = gen.generate([{"file": "x.py", "line": 1, "description": "t"}], "diff")
        assert "```" not in result["test_content"]

    def test_fallback_on_missing_key(self):
        client = MagicMock(spec=GeminiClient)
        client.generate.side_effect = MissingAPIKeyError("No key")
        gen = TestSuiteGenerator(gemini_client=client)
        result = gen.generate([{"file": "x.py", "line": 1, "description": "t"}], "diff")
        assert result["status"] == "fallback"
        assert result["test_content"] == _FALLBACK_TEST

    def test_fallback_on_rate_limit(self):
        client = MagicMock(spec=GeminiClient)
        client.generate.side_effect = RateLimitError(60)
        gen = TestSuiteGenerator(gemini_client=client)
        result = gen.generate([{"file": "x.py", "line": 1, "description": "t"}], "diff")
        assert result["status"] == "fallback"
