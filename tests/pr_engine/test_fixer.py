"""Tests para src/pr_engine/fixer.py — Generador de diffs."""

import pytest
from unittest.mock import MagicMock

from src.pr_engine.fixer import DiffFixer
from src.sdd_generator.ai_router import (
    UniversalAIRouter, AIProvider, ProviderError, SmartEngineProvider,
)


class MockDiffProvider(AIProvider):
    """Mock provider that returns a valid diff."""
    name = "MockAI"
    model = "mock"

    def __init__(self, response="--- a/config.py\n+++ b/config.py\n@@ -1,3 +1,3 @@\n-password = 'secret'\n+password = os.environ['DB_PASSWORD']\n"):
        self._response = response

    def is_available(self):
        return True

    def generate(self, prompt, system_prompt=""):
        return self._response


class FailProvider(AIProvider):
    """Provider that simulates 429."""
    name = "FailAI"
    model = "fail"

    def is_available(self):
        return True

    def generate(self, prompt, system_prompt=""):
        raise ProviderError(self.name, "Rate limit 429")


@pytest.fixture
def fixer():
    router = UniversalAIRouter(providers=[MockDiffProvider()])
    return DiffFixer(ai_router=router)


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
        router = UniversalAIRouter(providers=[MockDiffProvider(response="")])
        f = DiffFixer(ai_router=router)
        findings = [{"file": "x.py", "line": 1, "severity": "high",
                     "description": "test"}]
        result = f.generate(findings)
        assert result["status"] == "no_fix_needed"

    def test_gemini_429_during_fix_generation(self):
        """4.13: All providers fail → error status."""
        router = UniversalAIRouter(providers=[FailProvider(), SmartEngineProvider()])
        f = DiffFixer(ai_router=router)
        findings = [{"file": "x.py", "line": 1, "severity": "high",
                     "description": "test"}]
        result = f.generate(findings)
        assert result["status"] == "error"

    def test_missing_api_key_returns_error(self):
        """No cloud providers → SmartEngine → error (can't generate diffs)."""
        router = UniversalAIRouter(providers=[SmartEngineProvider()])
        f = DiffFixer(ai_router=router)
        findings = [{"file": "x.py", "line": 1, "severity": "high",
                     "description": "test"}]
        result = f.generate(findings)
        assert result["status"] == "error"

    def test_invalid_diff_detected(self):
        """4.18: Diff sin marcadores no es válido."""
        router = UniversalAIRouter(providers=[MockDiffProvider(response="no diff here just text")])
        f = DiffFixer(ai_router=router)
        findings = [{"file": "x.py", "line": 1, "severity": "high",
                     "description": "test"}]
        result = f.generate(findings)
        assert result["status"] == "no_fix_needed"

    def test_generate_returns_provider_info(self, fixer):
        findings = [{"file": "x.py", "line": 1, "severity": "high",
                     "description": "test"}]
        result = fixer.generate(findings)
        assert result["provider"] == "MockAI"
        assert "latency_ms" in result
