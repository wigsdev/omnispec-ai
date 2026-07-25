"""Tests EDGE-2: Repos vacíos, archivos > 256 KB, formatos no soportados.

Verifica manejo amigable de edge cases sin crasheos.
"""

import pytest

from src.auditor.scanner import AuditScanner, MAX_FILE_SIZE_KB


@pytest.fixture
def scanner():
    return AuditScanner()


class TestEmptyRepo:
    """Tests de repositorio vacío."""

    def test_empty_repo_returns_score_na(self, scanner):
        """Repo con 0 archivos retorna score: null."""
        result = scanner.scan("https://github.com/test/empty", files=[])
        assert result["score"] is None
        assert "N/A" in result["message"]

    def test_empty_repo_returns_200_not_500(self, scanner):
        """No crashea — retorna resultado estructurado."""
        result = scanner.scan("https://github.com/test/empty", files=[])
        assert result is not None
        assert "findings" in result

    def test_none_files_returns_score_na(self, scanner):
        """files=None retorna score N/A."""
        result = scanner.scan("https://github.com/test/empty", files=None)
        assert result["score"] is None


class TestFileOver256KB:
    """Tests de archivos > 256 KB."""

    def test_file_over_256kb_is_skipped(self, scanner):
        """Archivo > 256 KB aparece en 'skipped_files'."""
        files = [{"path": "big_file.py", "content": "x" * 1000, "size_kb": 300}]
        result = scanner.scan("https://github.com/test/repo", files)
        assert len(result["skipped_files"]) == 1
        assert result["skipped_files"][0]["reason"] == "exceeds_256kb_limit"
        assert result["skipped_files"][0]["size_kb"] == 300

    def test_file_exactly_256kb_is_analyzed(self, scanner):
        """Archivo de exactamente 256 KB SÍ se analiza."""
        files = [{"path": "ok.py", "content": "pass", "size_kb": 256}]
        result = scanner.scan("https://github.com/test/repo", files)
        assert len(result["skipped_files"]) == 0

    def test_file_over_limit_not_scanned_for_secrets(self, scanner):
        """Archivo skippeado NO se escanea (no genera findings)."""
        files = [{"path": "big.py", "content": "AKIAIOSFODNN7EXAMPLE", "size_kb": 300}]
        result = scanner.scan("https://github.com/test/repo", files)
        assert result["score"] is None  # No analyzable files
        assert result["findings"]["secrets"] == []


class TestUnsupportedFormats:
    """Tests de formatos no soportados."""

    def test_unsupported_formats_only_returns_extensions_list(self, scanner):
        """Repo con solo .png/.exe retorna extensions_found."""
        files = [
            {"path": "image.png", "content": "binary", "size_kb": 50},
            {"path": "app.exe", "content": "binary", "size_kb": 100},
        ]
        result = scanner.scan("https://github.com/test/repo", files)
        assert result["score"] is None
        assert ".png" in result["extensions_found"]
        assert ".exe" in result["extensions_found"]

    def test_mixed_supported_unsupported(self, scanner):
        """Archivos mixtos: soportados se analizan, no soportados se omiten."""
        files = [
            {"path": "app.py", "content": "pass", "size_kb": 1},
            {"path": "logo.png", "content": "binary", "size_kb": 50},
        ]
        result = scanner.scan("https://github.com/test/repo", files)
        assert result["score"] is not None  # app.py fue analizado
        assert len(result["skipped_files"]) == 1

    def test_max_file_size_constant_is_256(self):
        """La constante MAX_FILE_SIZE_KB es 256."""
        assert MAX_FILE_SIZE_KB == 256
