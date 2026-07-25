"""Tests para src/pr_engine/validator.py — Ejecutor pytest aislado."""

import pytest

from src.pr_engine.validator import PatchValidator


@pytest.fixture
def validator():
    return PatchValidator()


class TestPatchValidation:
    """Tests del validador de patches."""

    def test_passing_tests_return_passed_true(self, validator):
        test_code = "def test_ok(): assert True\n"
        result = validator.validate(test_code)
        assert result["passed"] is True
        assert result["return_code"] == 0

    def test_failing_tests_return_passed_false(self, validator):
        test_code = "def test_fail(): assert False, 'intentional'\n"
        result = validator.validate(test_code)
        assert result["passed"] is False
        assert result["return_code"] != 0

    def test_pytest_failure_blocks_pr_and_shows_output(self, validator):
        """4.17: Tests fallidos retornan stdout/stderr completo."""
        test_code = "def test_x(): assert 1 == 2\n"
        result = validator.validate(test_code)
        assert result["passed"] is False
        assert "assert 1 == 2" in result["output"] or "failed" in result["output"].lower()

    def test_empty_content_returns_failed(self, validator):
        result = validator.validate("")
        assert result["passed"] is False

    def test_syntax_error_returns_failed(self, validator):
        test_code = "def test_x(:\n    pass\n"
        result = validator.validate(test_code)
        assert result["passed"] is False

    def test_timeout_handled_gracefully(self, validator):
        """Tests que exceden timeout no crashean."""
        test_code = "import time\ndef test_slow(): time.sleep(0.1); assert True\n"
        result = validator.validate(test_code, timeout=5)
        assert result["passed"] is True
