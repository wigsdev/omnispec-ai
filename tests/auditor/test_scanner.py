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


class TestSupportedExtensions:
    """Tests de extensiones soportadas en el nuevo conjunto ampliado."""

    def test_javascript_file_is_analyzed(self, scanner):
        """Archivos .js son analizados."""
        files = [{"path": "server.js", "content": "const key = 'AKIAABCDEF1234567890'", "size_kb": 1}]
        result = scanner.scan("https://github.com/test/repo", files)
        assert result["score"] is not None
        assert len(result["findings"]["secrets"]) >= 1

    def test_typescript_file_is_analyzed(self, scanner):
        """Archivos .ts son analizados."""
        files = [{"path": "config.ts", "content": "export const API_KEY = 'abcdefghijklmnopqrstuvwxyz123'", "size_kb": 1}]
        result = scanner.scan("https://github.com/test/repo", files)
        assert result["score"] is not None

    def test_java_file_is_analyzed(self, scanner):
        """Archivos .java son analizados."""
        files = [{"path": "src/Config.java", "content": 'String url = "jdbc:mysql://user:pass@host/db"', "size_kb": 1}]
        result = scanner.scan("https://github.com/test/repo", files)
        assert result["score"] is not None

    def test_ruby_file_is_analyzed(self, scanner):
        """Archivos .rb son analizados."""
        files = [{"path": "config/database.rb", "content": "password = 'hunter2'", "size_kb": 1}]
        result = scanner.scan("https://github.com/test/repo", files)
        assert result["score"] is not None

    def test_go_file_is_analyzed(self, scanner):
        """Archivos .go son analizados."""
        files = [{"path": "main.go", "content": 'apiKey := "abcdefghijklmnopqrstuvwxyz1234"', "size_kb": 1}]
        result = scanner.scan("https://github.com/test/repo", files)
        assert result["score"] is not None

    def test_tfvars_file_is_analyzed(self, scanner):
        """Archivos .tfvars son analizados (variables Terraform con secrets)."""
        files = [{"path": "terraform.tfvars", "content": 'db_password = "s3cur3P4ss!"', "size_kb": 1}]
        result = scanner.scan("https://github.com/test/repo", files)
        assert result["score"] is not None
        assert len(result["findings"]["secrets"]) >= 1

    def test_xml_file_is_analyzed(self, scanner):
        """Archivos .xml son analizados (Maven settings, Spring configs)."""
        files = [{"path": "settings.xml", "content": "<password>mysecret123</password>", "size_kb": 1}]
        result = scanner.scan("https://github.com/test/repo", files)
        assert result["score"] is not None

    def test_env_local_file_is_analyzed(self, scanner):
        """Archivos .env.local son analizados."""
        files = [{"path": "frontend/.env.local", "content": "NEXT_PUBLIC_API_KEY=abcdefghijklmnopqrstu", "size_kb": 1}]
        result = scanner.scan("https://github.com/test/repo", files)
        assert result["score"] is not None

    def test_png_still_skipped(self, scanner):
        """Archivos binarios (.png) siguen siendo omitidos."""
        files = [{"path": "logo.png", "content": "binary", "size_kb": 5}]
        result = scanner.scan("https://github.com/test/repo", files)
        assert result["score"] is None
        assert len(result["skipped_files"]) == 1

    def test_woff_still_skipped(self, scanner):
        """Archivos de fuentes (.woff) siguen siendo omitidos."""
        files = [{"path": "font.woff", "content": "binary", "size_kb": 50}]
        result = scanner.scan("https://github.com/test/repo", files)
        assert result["score"] is None


class TestSpecialFilenames:
    """Tests de archivos sin extensión detectados por nombre (SPECIAL_FILENAMES)."""

    def test_dockerfile_is_analyzed(self, scanner):
        """Dockerfile (sin extensión) es analizado."""
        files = [{"path": "Dockerfile", "content": "ENV API_KEY=abcdefghijklmnopqrstuvwx", "size_kb": 1}]
        result = scanner.scan("https://github.com/test/repo", files)
        assert result["score"] is not None

    def test_makefile_is_analyzed(self, scanner):
        """Makefile es analizado."""
        files = [{"path": "Makefile", "content": "CIRCLE_TOKEN=abc123def456ghi789jkl", "size_kb": 1}]
        result = scanner.scan("https://github.com/test/repo", files)
        assert result["score"] is not None
        assert len(result["findings"]["secrets"]) >= 1

    def test_jenkinsfile_is_analyzed(self, scanner):
        """Jenkinsfile es analizado."""
        files = [{"path": "Jenkinsfile", "content": "password = 'jenkins_secret_123'", "size_kb": 1}]
        result = scanner.scan("https://github.com/test/repo", files)
        assert result["score"] is not None

    def test_npmrc_file_is_analyzed(self, scanner):
        """.npmrc es analizado (puede estar en SPECIAL_FILENAMES o extensión)."""
        files = [{"path": ".npmrc", "content": "//registry.npmjs.org/:_authToken=npm_ABCDEFGHIJKLMNOPQRST1234", "size_kb": 1}]
        result = scanner.scan("https://github.com/test/repo", files)
        assert result["score"] is not None
        assert len(result["findings"]["secrets"]) >= 1

    def test_nested_dockerfile_is_analyzed(self, scanner):
        """Dockerfile en subdirectorio también es reconocido."""
        files = [{"path": "docker/Dockerfile", "content": "ENV DB_PASS=mysecret123", "size_kb": 1}]
        result = scanner.scan("https://github.com/test/repo", files)
        assert result["score"] is not None


class TestGetBasenameAndExtension:
    """Tests del helper _get_basename y _get_extension."""

    def test_get_basename_unix_path(self, scanner):
        assert scanner._get_basename("src/api/config.py") == "config.py"

    def test_get_basename_root_file(self, scanner):
        assert scanner._get_basename("Dockerfile") == "Dockerfile"

    def test_get_basename_dotfile(self, scanner):
        assert scanner._get_basename(".env") == ".env"

    def test_get_extension_simple(self, scanner):
        assert scanner._get_extension("config.py") == ".py"

    def test_get_extension_compound_env_local(self, scanner):
        assert scanner._get_extension("frontend/.env.local") == ".env.local"

    def test_get_extension_compound_env_production(self, scanner):
        assert scanner._get_extension(".env.production") == ".env.production"

    def test_get_extension_no_extension(self, scanner):
        assert scanner._get_extension("Dockerfile") == ""

    def test_get_extension_dotfile(self, scanner):
        assert scanner._get_extension(".npmrc") == ".npmrc"
