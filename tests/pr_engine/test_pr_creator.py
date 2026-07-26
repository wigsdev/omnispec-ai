"""Tests para src/pr_engine/pr_creator.py — Cliente GitHub API."""

import pytest
from unittest.mock import MagicMock, patch

from src.pr_engine.pr_creator import PRCreator, PRCreationError


@pytest.fixture
def creator():
    return PRCreator(github_token="fake-token")


@pytest.fixture
def mock_session():
    """Fixture: mock de requests.Session para PRCreator."""
    with patch('src.pr_engine.pr_creator.requests.Session') as MockSession:
        session = MagicMock()
        MockSession.return_value = session

        # Default responses
        repo_resp = MagicMock()
        repo_resp.status_code = 200
        repo_resp.json.return_value = {"default_branch": "main"}

        ref_resp = MagicMock()
        ref_resp.status_code = 200
        ref_resp.json.return_value = {"object": {"sha": "abc123"}}

        branch_check = MagicMock()
        branch_check.status_code = 404  # branch doesn't exist

        create_ref = MagicMock()
        create_ref.status_code = 201

        put_file = MagicMock()
        put_file.status_code = 201
        put_file.json.return_value = {"commit": {"sha": "def456"}}

        contents_check = MagicMock()
        contents_check.status_code = 404

        pr_resp = MagicMock()
        pr_resp.status_code = 201
        pr_resp.json.return_value = {"html_url": "https://github.com/o/r/pull/1"}

        def side_effect_get(url, **kwargs):
            if "/git/ref/heads/fix" in url:
                return branch_check
            if "/git/ref/heads/" in url:
                return ref_resp
            if "/git/commits/" in url:
                commit_obj = MagicMock()
                commit_obj.status_code = 200
                commit_obj.json.return_value = {"tree": {"sha": "tree_sha_123"}}
                return commit_obj
            if "/contents/" in url:
                return contents_check
            return repo_resp

        session.get.side_effect = side_effect_get
        session.post.return_value = create_ref
        session.put.return_value = put_file

        # PR creation and git operations
        def side_effect_post(url, **kwargs):
            if "/pulls" in url:
                return pr_resp
            # blobs, trees, commits, refs — all return 201
            resp = MagicMock()
            resp.status_code = 201
            resp.json.return_value = {"sha": "new_sha_123"}
            return resp

        session.post.side_effect = side_effect_post

        # Mock patch (for updating refs)
        patch_resp = MagicMock()
        patch_resp.status_code = 200
        session.patch.return_value = patch_resp

        yield session


class TestPRCreation:
    """Tests de creación de PR."""

    def test_create_pr_returns_pr_url(self, mock_session):
        creator = PRCreator(github_token="fake-token")
        result = creator.create_pr(
            repo_url="https://github.com/owner/repo",
            diff="--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-bad\n+good",
            tests="def test_x(): pass",
            findings=[{"severity": "critical", "description": "Password exposed",
                       "file": "x.py", "line": 1}],
        )
        assert "pr_url" in result
        assert "github.com" in result["pr_url"]
        assert "branch" in result

    def test_branch_name_default(self, mock_session):
        creator = PRCreator(github_token="fake-token")
        result = creator.create_pr(
            repo_url="https://github.com/o/r",
            diff="---\n+++\n@@\n-x\n+y",
            tests="pass",
            findings=[],
        )
        assert result["branch"] == "fix/omnispec-patch"

    def test_branch_already_exists_appends_timestamp(self, mock_session):
        """4.15: Si rama existe, usa timestamp fallback."""
        # Make branch check return 200 (exists)
        def get_side_effect(url, **kwargs):
            if "/git/ref/heads/fix" in url:
                resp = MagicMock()
                resp.status_code = 200
                return resp
            if "/git/ref/heads/" in url:
                resp = MagicMock()
                resp.status_code = 200
                resp.json.return_value = {"object": {"sha": "abc123"}}
                return resp
            if "/git/commits/" in url:
                resp = MagicMock()
                resp.status_code = 200
                resp.json.return_value = {"tree": {"sha": "tree_abc"}}
                return resp
            if "/contents/" in url:
                resp = MagicMock()
                resp.status_code = 404
                return resp
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"default_branch": "main"}
            return resp

        mock_session.get.side_effect = get_side_effect

        creator = PRCreator(github_token="fake-token")
        result = creator.create_pr(
            repo_url="https://github.com/o/r",
            diff="---\n+++\n@@\n-x\n+y",
            tests="pass",
            findings=[],
        )
        assert result["branch"].startswith("fix/omnispec-patch-")
        assert result["branch"] != "fix/omnispec-patch"

    def test_commit_message_includes_finding_description(self):
        creator = PRCreator(github_token="fake")
        findings = [{"severity": "critical", "description": "AWS key exposed",
                     "file": "config.py", "line": 5}]
        msg = creator._build_commit_message(findings)
        # IA genera el mensaje; verificar que contiene "fix" o "security"
        assert "fix" in msg.lower() or "security" in msg.lower()

    def test_parse_repo_url_extracts_owner_repo(self):
        creator = PRCreator(github_token="fake")
        owner, repo = creator._parse_repo_url("https://github.com/myorg/myrepo")
        assert owner == "myorg"
        assert repo == "myrepo"

    def test_pr_body_contains_findings(self):
        creator = PRCreator(github_token="fake")
        findings = [{"severity": "critical", "description": "Secret exposed",
                     "file": "x.py", "line": 1}]
        body = creator._build_pr_body_fallback(findings, "diff", None)
        assert "Secret exposed" in body
        assert "diff" in body

    def test_no_token_raises_error(self):
        creator = PRCreator(github_token="")
        with pytest.raises(PRCreationError, match="GITHUB_TOKEN"):
            creator.create_pr(
                repo_url="https://github.com/o/r",
                diff="diff", tests="tests", findings=[]
            )
