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
        assert result["status"] in ("no_fix_needed", "error")

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
        assert result["status"] in ("no_fix_needed", "error")

    def test_generate_returns_provider_info(self, fixer):
        findings = [{"file": "x.py", "line": 1, "severity": "high",
                     "description": "test"}]
        result = fixer.generate(findings)
        assert result["provider"] == "MockAI"
        assert "latency_ms" in result


class TestSeverityFiltering:
    """Tests del filtro de severidades accionables."""

    def test_info_findings_only_returns_no_fix_needed(self, fixer):
        """Findings con severidad 'info' (archivos de test) → no fix."""
        findings = [
            {"file": "tests/test_structural.py", "line": 22, "severity": "info",
             "description": "AWS Access Key expuesta", "in_test_file": True},
            {"file": "tests/test_scanner.py", "line": 52, "severity": "info",
             "description": "Password hardcoded en código", "in_test_file": True},
        ]
        result = fixer.generate(findings)
        assert result["status"] == "no_fix_needed"
        assert result.get("skipped") == 2

    def test_low_findings_only_returns_no_fix_needed(self, fixer):
        """Findings con severidad 'low' (valores de ejemplo) → no fix automático."""
        findings = [
            {"file": "src/auditor/structural.py", "line": 61, "severity": "low",
             "description": "AWS Access Key expuesta"},
        ]
        result = fixer.generate(findings)
        assert result["status"] == "no_fix_needed"
        assert result.get("skipped") == 1

    def test_mixed_severities_only_processes_actionable(self, fixer):
        """Mix de severidades: solo critical/high/medium se procesan."""
        findings = [
            {"file": "tests/test_structural.py", "line": 22, "severity": "info",
             "description": "AWS key en test"},
            {"file": "src/config.py", "line": 5, "severity": "critical",
             "description": "Password hardcoded real"},
        ]
        result = fixer.generate(findings)
        # El finding crítico sí genera un diff
        assert result["status"] == "generated"
        # Informa que se excluyó 1 finding info
        assert result.get("skipped_low_info") == 1

    def test_critical_findings_are_not_filtered(self, fixer):
        """Findings críticos siempre pasan el filtro."""
        findings = [{"file": "config.py", "line": 1, "severity": "critical",
                     "description": "Password hardcoded"}]
        result = fixer.generate(findings)
        assert result["status"] == "generated"
