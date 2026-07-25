"""Tests para src/auditor/scanner.py — Orquestador de auditoría."""

import pytest

from src.auditor.scanner import AuditScanner, MAX_FILE_SIZE_KB


@pytest.fixture
def scanner():
    return AuditScanner()


class TestScannerOrchestration:
    """Tests del flujo principal de escaneo."""

    def test_scan_returns_score(self, scanner):
        files = [{"path": "app.py", "content": "print('hello')", "size_kb": 1}]
        result = scanner.scan("https://github.com/test/repo", files)
        assert "score" in result
        assert isinstance(result["score"], (int, float))

    def test_scan_returns_findings_by_category(self, scanner):
        files = [{"path": "app.py", "content": "pass", "size_kb": 1}]
        result = scanner.scan("https://github.com/test/repo", files)
        assert "findings" in result
        assert "secrets" in result["findings"]
        assert "iac" in result["findings"]
        assert "governance" in result["findings"]

    def test_scan_detects_secret_in_file(self, scanner):
        files = [{"path": "config.py", "content": "key = 'AKIAIOSFODNN7EXAMPLE'", "size_kb": 1}]
        result = scanner.scan("https://github.com/test/repo", files)
        assert len(result["findings"]["secrets"]) >= 1

    def test_score_100_for_clean_repo(self, scanner):
        files = [
            {"path": "src/app.py", "content": "print('hello')", "size_kb": 1},
            {"path": "README.md", "content": "# Clean", "size_kb": 1},
            {"path": "tests/test_app.py", "content": "def test(): pass", "size_kb": 1},
            {"path": "CHANGELOG.md", "content": "# Changes", "size_kb": 1},
        ]
        result = scanner.scan("https://github.com/test/repo", files)
        assert result["score"] == 100.0


class TestScoreClamping:
    """Tests de acotación del score (3.19)."""

    def test_score_clamped_at_zero(self, scanner):
        """Penalties excesivas producen score = 0, no negativo."""
        # 10 critical secrets = penalty 200, weighted = 100 → score = 0
        content = "\n".join([f"password = 'secret{i}'" for i in range(10)])
        files = [{"path": "config.py", "content": content, "size_kb": 5}]
        result = scanner.scan("https://github.com/test/repo", files)
        assert result["score"] >= 0
        assert result["score"] == 0

    def test_score_never_exceeds_100(self, scanner):
        files = [
            {"path": "app.py", "content": "clean code", "size_kb": 1},
            {"path": "README.md", "content": "# Docs", "size_kb": 1},
            {"path": "tests/test_x.py", "content": "pass", "size_kb": 1},
            {"path": "CHANGELOG.md", "content": "# Log", "size_kb": 1},
        ]
        result = scanner.scan("https://github.com/test/repo", files)
        assert result["score"] <= 100


class TestGemini429Fallback:
    """Test 3.18: Gemini 429 durante explicación usa texto genérico."""

    def test_gemini_429_during_explanation_uses_generic_text(self):
        """Verificar fallback genérico cuando Gemini 429 en Role-2."""
        from unittest.mock import MagicMock
        from src.auditor.explainer import RiskExplainer, GENERIC_EXPLANATION
        from src.sdd_generator.gemini_client import GeminiClient, RateLimitError

        client = MagicMock(spec=GeminiClient)
        client.is_available = True
        client.generate.side_effect = RateLimitError(retry_after=60)

        explainer = RiskExplainer(gemini_client=client)
        findings = [{"file": "x.py", "line": 1, "type": "aws_access_key",
                     "severity": "critical", "description": "AWS key exposed"}]

        result = explainer.explain_findings(findings)
        assert result[0]["explanation"] == GENERIC_EXPLANATION
