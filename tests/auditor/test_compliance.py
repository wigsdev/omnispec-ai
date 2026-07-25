"""Tests para src/auditor/compliance.py — Verificador de gobierno."""

import pytest

from src.auditor.compliance import GovernanceChecker, REQUIRED_TAGS


@pytest.fixture
def checker():
    return GovernanceChecker()


class TestDocumentationCheck:
    """Tests de verificación de documentación."""

    def test_missing_readme_detected(self, checker):
        files = [{"path": "src/app.py", "content": "pass"}]
        findings = checker.check(files)
        types = [f["type"] for f in findings]
        assert "missing_readme" in types

    def test_readme_present_no_finding(self, checker):
        files = [
            {"path": "README.md", "content": "# Project"},
            {"path": "src/app.py", "content": "pass"},
        ]
        findings = checker.check(files)
        types = [f["type"] for f in findings]
        assert "missing_readme" not in types

    def test_missing_tests_detected(self, checker):
        files = [{"path": "src/app.py", "content": "pass"}]
        findings = checker.check(files)
        types = [f["type"] for f in findings]
        assert "missing_tests" in types

    def test_tests_present_no_finding(self, checker):
        files = [
            {"path": "tests/test_app.py", "content": "def test(): pass"},
        ]
        findings = checker.check(files)
        types = [f["type"] for f in findings]
        assert "missing_tests" not in types


class TestTagsCheck:
    """Tests de verificación de tags obligatorios."""

    def test_missing_tags_in_iac_file(self, checker):
        files = [{"path": "infra/stack.json", "content": '{"resource": "AWS::Lambda"}'}]
        findings = checker.check(files)
        tag_findings = [f for f in findings if f["type"] == "missing_tags"]
        assert len(tag_findings) >= 1

    def test_all_tags_present_no_finding(self, checker):
        content = "resource AWS Environment Owner Project CostCenter"
        files = [{"path": "infra/stack.json", "content": content}]
        findings = checker.check(files)
        tag_findings = [f for f in findings if f["type"] == "missing_tags"]
        assert len(tag_findings) == 0
