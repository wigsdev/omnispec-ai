"""Tests para src/pr_engine/pr_creator.py — Cliente GitHub API."""

import pytest
from unittest.mock import MagicMock, patch

from src.pr_engine.pr_creator import PRCreator


@pytest.fixture
def creator():
    return PRCreator(github_token="fake-token")


class TestPRCreation:
    """Tests de creación de PR."""

    def test_create_pr_returns_pr_url(self, creator):
        result = creator.create_pr(
            repo_url="https://github.com/owner/repo",
            diff="--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-bad\n+good",
            tests="def test_x(): pass",
            findings=[{"severity": "critical", "description": "Password exposed",
                       "file": "x.py", "line": 1}],
        )
        assert "pr_url" in result
        assert "branch" in result

    def test_branch_name_default(self, creator):
        result = creator.create_pr(
            repo_url="https://github.com/o/r",
            diff="---\n+++\n@@\n-x\n+y",
            tests="pass",
            findings=[],
        )
        assert result["branch"] == "fix/omnispec-patch"

    def test_branch_already_exists_appends_timestamp(self):
        """4.15: Si rama existe, usa timestamp fallback."""
        creator = PRCreator(github_token="fake")
        creator._branch_exists = MagicMock(return_value=True)
        result = creator.create_pr(
            repo_url="https://github.com/o/r",
            diff="---\n+++\n@@\n-x\n+y",
            tests="pass",
            findings=[],
        )
        assert result["branch"].startswith("fix/omnispec-patch-")
        assert result["branch"] != "fix/omnispec-patch"

    def test_commit_message_includes_finding_description(self, creator):
        findings = [{"severity": "critical", "description": "AWS key exposed",
                     "file": "config.py", "line": 5}]
        msg = creator._build_commit_message(findings)
        assert msg.startswith("fix(security):")
        assert "AWS key exposed" in msg

    def test_parse_repo_url_extracts_owner_repo(self, creator):
        owner, repo = creator._parse_repo_url("https://github.com/myorg/myrepo")
        assert owner == "myorg"
        assert repo == "myrepo"

    def test_pr_body_contains_findings(self, creator):
        findings = [{"severity": "critical", "description": "Secret exposed",
                     "file": "x.py", "line": 1}]
        body = creator._build_pr_body(findings, "diff", "tests")
        assert "Secret exposed" in body
        assert "diff" in body
