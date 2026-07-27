"""Tests para src/auditor/structural.py — Detector de secretos.

Valida la detección de los 15 patrones de secretos con regex non-greedy.
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


class TestConnectionStringDetection:
    """Tests de detección de connection strings con credenciales embebidas."""

    def test_detects_jdbc_connection_string(self, detector):
        content = "url = 'jdbc:mysql://user:s3cr3tP4ss@prod-db.example.com:3306/mydb'"
        files = [{"path": "src/db.java", "content": content}]
        findings = detector.scan(files)
        assert len(findings) >= 1
        types = [f["type"] for f in findings]
        assert "connection_string_db" in types

    def test_detects_mongodb_connection_string(self, detector):
        content = "MONGO_URI=mongodb://admin:hunter2@cluster0.mongodb.net/prod"
        files = [{"path": ".env", "content": content}]
        findings = detector.scan(files)
        assert any(f["type"] == "connection_string_db" for f in findings)

    def test_detects_postgresql_connection_string(self, detector):
        content = 'DB_URL = "postgresql://postgres:mypassword@localhost:5432/app"'
        files = [{"path": "config.py", "content": content}]
        findings = detector.scan(files)
        assert any(f["type"] == "connection_string_db" for f in findings)

    def test_no_false_positive_connection_string_without_password(self, detector):
        """URL sin credenciales no debe disparar la detección."""
        content = "DB_URL=postgresql://localhost:5432/mydb"
        files = [{"path": "config.py", "content": content}]
        findings = detector.scan(files)
        conn_findings = [f for f in findings if f["type"] == "connection_string_db"]
        assert len(conn_findings) == 0


class TestGenericAPIKeyDetection:
    """Tests de detección de API keys y secrets genéricos."""

    def test_detects_api_key_assignment(self, detector):
        content = 'api_key = "sk-abcdef1234567890abcdef1234567890"'
        files = [{"path": "config.py", "content": content}]
        findings = detector.scan(files)
        assert any(f["type"] == "generic_api_key" for f in findings)

    def test_detects_apikey_json(self, detector):
        content = '{"apikey": "abcdef1234567890abcdef1234567890"}'
        files = [{"path": "config.json", "content": content}]
        findings = detector.scan(files)
        assert any(f["type"] == "generic_api_key" for f in findings)

    def test_detects_x_api_key_header(self, detector):
        content = 'headers["x-api-key"] = "abcdefghijklmnopqrstuvwx"'
        files = [{"path": "client.js", "content": content}]
        findings = detector.scan(files)
        assert any(f["type"] == "generic_api_key" for f in findings)

    def test_detects_client_secret(self, detector):
        content = 'client_secret = "mysupersecretvalue1234"'
        files = [{"path": "oauth.py", "content": content}]
        findings = detector.scan(files)
        assert any(f["type"] == "generic_secret" for f in findings)

    def test_generic_api_key_severity_is_high(self, detector):
        content = 'api_key = "abcdefghijklmnopqrstuvwxyz1234"'
        files = [{"path": "config.py", "content": content}]
        findings = [f for f in detector.scan(files) if f["type"] == "generic_api_key"]
        assert findings[0]["severity"] == "high"
        assert findings[0]["penalty"] == 15


class TestPlatformTokenDetection:
    """Tests de tokens de plataformas específicas."""

    def test_detects_github_pat_token(self, detector):
        content = "token = 'ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456'"
        files = [{"path": "deploy.sh", "content": content}]
        findings = detector.scan(files)
        assert any(f["type"] == "github_token" for f in findings)
        gh_findings = [f for f in findings if f["type"] == "github_token"]
        assert gh_findings[0]["severity"] == "critical"

    def test_detects_github_oauth_token(self, detector):
        content = "GITHUB_TOKEN=gho_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"
        files = [{"path": ".env", "content": content}]
        findings = detector.scan(files)
        assert any(f["type"] == "github_token" for f in findings)

    def test_detects_slack_bot_token(self, detector):
        # Construido dinámicamente para evitar GitHub Secret Scanning
        prefix = "xox" + "b"
        suffix = "-0" * 10 + "-" + "F" * 20
        content = f"SLACK_TOKEN={prefix}{suffix}"
        files = [{"path": "config.yaml", "content": content}]
        findings = detector.scan(files)
        assert any(f["type"] == "slack_token" for f in findings)

    def test_detects_stripe_live_key(self, detector):
        # Construido dinámicamente para evitar GitHub Secret Scanning
        prefix = "sk" + "_" + "live" + "_"
        value = prefix + "F" * 24
        content = f"STRIPE_KEY={value}"
        files = [{"path": "payments.js", "content": content}]
        findings = detector.scan(files)
        assert any(f["type"] == "stripe_key" for f in findings)
        stripe = [f for f in findings if f["type"] == "stripe_key"]
        assert stripe[0]["severity"] == "critical"

    def test_detects_stripe_test_key(self, detector):
        """Claves de test de Stripe también se reportan (pueden estar en producción)."""
        # Construido dinámicamente para evitar GitHub Secret Scanning
        prefix = "sk" + "_" + "test" + "_"
        value = prefix + "F" * 24
        content = f"STRIPE_KEY={value}"
        files = [{"path": "payments.py", "content": content}]
        findings = detector.scan(files)
        assert any(f["type"] == "stripe_key" for f in findings)

    def test_detects_ci_token_hardcoded(self, detector):
        content = "CIRCLE_TOKEN=abc123def456ghi789jkl"
        files = [{"path": "Makefile", "content": content}]
        findings = detector.scan(files)
        assert any(f["type"] == "ci_token_hardcoded" for f in findings)


class TestGoogleCredentialDetection:
    """Tests de detección de credenciales Google Cloud."""

    def test_detects_google_service_account_json(self, detector):
        content = '{"type": "service_account", "project_id": "my-project"}'
        files = [{"path": "credentials.json", "content": content}]
        findings = detector.scan(files)
        assert any(f["type"] == "google_service_account" for f in findings)
        sa = [f for f in findings if f["type"] == "google_service_account"]
        assert sa[0]["severity"] == "critical"

    def test_detects_google_api_key(self, detector):
        content = "GOOGLE_API_KEY=AIzaSyAbcDefGhiJklMnoPqrStuvWxYz1234567"
        files = [{"path": "config.js", "content": content}]
        findings = detector.scan(files)
        assert any(f["type"] == "google_api_key" for f in findings)

    def test_no_false_positive_type_field(self, detector):
        """Campo 'type' con otro valor no es un service account."""
        content = '{"type": "oauth2", "project_id": "my-project"}'
        files = [{"path": "config.json", "content": content}]
        findings = detector.scan(files)
        assert not any(f["type"] == "google_service_account" for f in findings)


class TestNPMTokenDetection:
    """Tests de detección de tokens NPM en .npmrc."""

    def test_detects_npm_auth_token(self, detector):
        content = "//registry.npmjs.org/:_authToken=npm_ABCDEFGHIJKLMNOPQRST1234567890"
        files = [{"path": ".npmrc", "content": content}]
        findings = detector.scan(files)
        assert any(f["type"] == "npm_auth_token" for f in findings)
        npm = [f for f in findings if f["type"] == "npm_auth_token"]
        assert npm[0]["severity"] == "critical"

    def test_detects_github_packages_token(self, detector):
        content = "//npm.pkg.github.com/:_authToken=ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"
        files = [{"path": ".npmrc", "content": content}]
        findings = detector.scan(files)
        # Puede matchear github_token o npm_auth_token — ambos son válidos
        token_types = {f["type"] for f in findings}
        assert token_types & {"npm_auth_token", "github_token"}
