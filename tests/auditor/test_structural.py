"""Tests para src/auditor/structural.py — Detector de secretos.

Valida la detección de los 4 patrones de secretos con regex non-greedy.
Verifica que NO se almacenan valores de secretos (AC-2.2.3).
"""

import pytest

from src.auditor.structural import SecretsDetector


@pytest.fixture
def detector():
    return SecretsDetector()


class TestAWSKeyDetection:
    """Tests de detección de AWS Access Keys."""

    def test_detects_aws_access_key(self, detector):
        files = [{"path": "config.py", "content": "key = 'AKIAIOSFODNN7EXAMPLE'"}]
        findings = detector.scan(files)
        assert len(findings) == 1
        assert findings[0]["type"] == "aws_access_key"
        # AKIAIOSFODNN7EXAMPLE es el ejemplo canónico de AWS docs → severidad 'low'
        # (valor conocido como ejemplo, no una clave real filtrada)
        assert findings[0]["severity"] == "low"

    def test_detects_aws_key_in_env_file(self, detector):
        files = [{"path": ".env", "content": "AWS_KEY=AKIAIOSFODNN7EXAMPLE"}]
        findings = detector.scan(files)
        assert len(findings) == 1

    def test_detects_real_aws_key_as_critical(self, detector):
        """Una clave AWS que no es ejemplo conocido → severidad 'critical'."""
        files = [{"path": "config.py", "content": "key = 'AKIAABCDEF1234567890'"}]
        findings = detector.scan(files)
        assert len(findings) == 1
        assert findings[0]["severity"] == "critical"
        assert findings[0]["penalty"] == 20

    def test_aws_key_in_test_file_is_info(self, detector):
        """AWS key (no ejemplo) en archivo de test → severidad 'info', penalty 0."""
        files = [{"path": "tests/test_config.py", "content": "key = 'AKIAABCDEF1234567890'"}]
        findings = detector.scan(files)
        assert len(findings) == 1
        assert findings[0]["severity"] == "info"
        assert findings[0]["penalty"] == 0

    def test_known_example_in_test_file_is_discarded(self, detector):
        """Valor de ejemplo canónico en archivo de test → descartado completamente."""
        files = [{"path": "tests/test_structural.py", "content": "key = 'AKIAIOSFODNN7EXAMPLE'"}]
        findings = detector.scan(files)
        assert len(findings) == 0
        files = [{"path": "x.py", "content": "AKIA_SHORT"}]
        findings = detector.scan(files)
        assert len(findings) == 0


class TestPasswordDetection:
    """Tests de detección de passwords hardcoded."""

    def test_detects_password_single_quotes(self, detector):
        files = [{"path": "db.py", "content": "password = 'my_secret_123'"}]
        findings = detector.scan(files)
        assert len(findings) == 1
        assert findings[0]["type"] == "password_assignment"

    def test_detects_password_double_quotes(self, detector):
        files = [{"path": "db.py", "content": 'passwd = "hunter2"'}]
        findings = detector.scan(files)
        assert len(findings) == 1

    def test_detects_pwd_variant(self, detector):
        files = [{"path": "x.py", "content": "pwd: 'abc123'"}]
        findings = detector.scan(files)
        assert len(findings) == 1

    def test_no_false_positive_empty_password(self, detector):
        files = [{"path": "x.py", "content": "password = ''"}]
        findings = detector.scan(files)
        assert len(findings) == 0


class TestBearerTokenDetection:
    """Tests de detección de Bearer/JWT tokens."""

    def test_detects_bearer_token(self, detector):
        files = [{"path": "api.py", "content": "Authorization Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.sig"}]
        findings = detector.scan(files)
        assert len(findings) == 1
        assert findings[0]["type"] == "bearer_token"


class TestPrivateKeyDetection:
    """Tests de detección de claves privadas PEM."""

    def test_detects_rsa_private_key(self, detector):
        files = [{"path": "key.pem", "content": "-----BEGIN RSA PRIVATE KEY-----\nMIIE..."}]
        findings = detector.scan(files)
        assert len(findings) == 1
        assert findings[0]["type"] == "private_key"

    def test_detects_ec_private_key(self, detector):
        files = [{"path": "k.pem", "content": "-----BEGIN EC PRIVATE KEY-----"}]
        findings = detector.scan(files)
        assert len(findings) == 1

    def test_detects_generic_private_key(self, detector):
        files = [{"path": "k.pem", "content": "-----BEGIN PRIVATE KEY-----"}]
        findings = detector.scan(files)
        assert len(findings) == 1


class TestMetadataOnly:
    """Tests de que NO se almacenan valores de secretos (AC-2.2.3)."""

    def test_finding_does_not_contain_secret_value(self, detector):
        secret = "AKIAIOSFODNN7EXAMPLE"
        files = [{"path": "x.py", "content": f"key = '{secret}'"}]
        findings = detector.scan(files)
        for finding in findings:
            for value in finding.values():
                if isinstance(value, str):
                    assert secret not in value

    def test_finding_contains_file_and_line(self, detector):
        files = [{"path": "config.py", "content": "line1\npassword = 'x'\nline3"}]
        findings = detector.scan(files)
        assert findings[0]["file"] == "config.py"
        assert findings[0]["line"] == 2
