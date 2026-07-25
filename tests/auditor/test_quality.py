"""Tests para src/auditor/quality.py — Inspector IaC AWS.

Valida detección de IAM Action:* / Resource:* y SG 0.0.0.0/0.
"""

import pytest

from src.auditor.quality import IaCInspector


@pytest.fixture
def inspector():
    return IaCInspector()


class TestIAMWildcards:
    """Tests de detección de IAM wildcards."""

    def test_detects_action_wildcard_json(self, inspector):
        files = [{"path": "infra/stack.json", "content": '"Action": "*"'}]
        findings = inspector.scan(files)
        assert len(findings) >= 1
        assert findings[0]["type"] == "iam_action_wildcard"

    def test_detects_action_wildcard_yaml(self, inspector):
        files = [{"path": "infra/stack.yaml", "content": "Action: '*'"}]
        findings = inspector.scan(files)
        assert len(findings) >= 1

    def test_detects_action_wildcard_list(self, inspector):
        files = [{"path": "infra/stack.json", "content": '"Action": ["*"]'}]
        findings = inspector.scan(files)
        assert len(findings) >= 1

    def test_detects_resource_wildcard(self, inspector):
        files = [{"path": "infra/stack.json", "content": '"Resource": "*"'}]
        findings = inspector.scan(files)
        assert len(findings) >= 1
        assert findings[0]["type"] == "iam_resource_wildcard"

    def test_no_detection_in_non_iac_file(self, inspector):
        files = [{"path": "src/app.py", "content": '"Action": "*"'}]
        findings = inspector.scan(files)
        assert len(findings) == 0

    def test_includes_cis_reference(self, inspector):
        files = [{"path": "infra/stack.json", "content": '"Action": "*"'}]
        findings = inspector.scan(files)
        assert "CIS" in findings[0]["reference"]


class TestSecurityGroups:
    """Tests de detección de Security Groups abiertos."""

    def test_detects_open_sg_with_sensitive_port(self, inspector):
        content = 'FromPort: 22\nCidrIp: "0.0.0.0/0"'
        files = [{"path": "infra/stack.yaml", "content": content}]
        findings = inspector.scan(files)
        assert len(findings) >= 1
        assert findings[0]["type"] == "open_security_group"

    def test_detects_open_sg_port_3389(self, inspector):
        content = 'FromPort: 3389\nCidrIp: "0.0.0.0/0"'
        files = [{"path": "infra/stack.yaml", "content": content}]
        findings = inspector.scan(files)
        assert len(findings) >= 1

    def test_detects_open_sg_without_port_context(self, inspector):
        content = 'CidrIp: "0.0.0.0/0"'
        files = [{"path": "infra/stack.yaml", "content": content}]
        findings = inspector.scan(files)
        assert len(findings) >= 1

    def test_terraform_cidr_blocks(self, inspector):
        content = 'cidr_blocks = ["0.0.0.0/0"]'
        files = [{"path": "infra/main.tf", "content": content}]
        findings = inspector.scan(files)
        assert len(findings) >= 1
