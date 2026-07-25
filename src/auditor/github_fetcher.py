"""GitHubFetcher — Descarga archivos de repositorios GitHub via API.

Usa la GitHub REST API v3 para listar y descargar archivos
de repositorios públicos (o privados con token).
Respeta el límite de 256 KB por archivo y filtra extensiones.

Attributes:
    GITHUB_API_BASE: URL base de la API de GitHub.
    SUPPORTED_EXTENSIONS: Extensiones que se analizan.
"""

import os
import base64
from typing import Any
from urllib.parse import urlparse

import requests

GITHUB_API_BASE = "https://api.github.com"

# Extensiones analizables (incluye .pem para detección de keys)
SUPPORTED_EXTENSIONS = {
    '.py', '.yaml', '.yml', '.json', '.tf', '.template',
    '.cfg', '.toml', '.env', '.pem', '.key', '.sh',
    '.js', '.ts', '.rb', '.go', '.java', '.xml',
}

MAX_FILE_SIZE_KB = 256
MAX_FILES_TO_FETCH = 100


class GitHubFetchError(Exception):
    """Error al descargar archivos de GitHub."""
    pass


class GitHubFetcher:
    """Cliente para descargar archivos de repositorios GitHub.

    Usa la API REST v3 de GitHub para obtener el tree de archivos
    y descargar el contenido de cada uno.
    """

    def __init__(self, token: str | None = None):
        """Inicializa el fetcher.

        Args:
            token: GitHub personal access token. Si None, lee de env.
        """
        self._token = token or os.environ.get("GITHUB_TOKEN", "")
        self._session = requests.Session()
        if self._token:
            self._session.headers["Authorization"] = f"Bearer {self._token}"
        self._session.headers["Accept"] = "application/vnd.github.v3+json"
        self._session.headers["User-Agent"] = "OmniSpec-AI-Auditor/1.0"

    def fetch_repo_files(self, repo_url: str) -> list[dict[str, Any]]:
        """Descarga archivos analizables de un repositorio.

        Args:
            repo_url: URL del repositorio (https://github.com/owner/repo).

        Returns:
            Lista de dicts con 'path', 'content', 'size_kb'.

        Raises:
            GitHubFetchError: Si no se puede acceder al repositorio.
        """
        owner, repo = self._parse_repo_url(repo_url)
        tree = self._get_repo_tree(owner, repo)

        files = []
        for item in tree:
            if item.get("type") != "blob":
                continue

            path = item.get("path", "")
            size_bytes = item.get("size", 0)
            size_kb = size_bytes / 1024

            # Skip archivos grandes
            if size_kb > MAX_FILE_SIZE_KB:
                files.append({
                    "path": path,
                    "content": "",
                    "size_kb": round(size_kb, 1),
                    "skipped": True,
                    "reason": "exceeds_256kb_limit",
                })
                continue

            # Solo descargar extensiones soportadas
            ext = self._get_extension(path)
            if ext not in SUPPORTED_EXTENSIONS and ext != '':
                files.append({
                    "path": path,
                    "content": "",
                    "size_kb": round(size_kb, 1),
                    "skipped": True,
                    "reason": f"unsupported_extension: {ext}",
                })
                continue

            # Descargar contenido
            if len(files) < MAX_FILES_TO_FETCH:
                content = self._get_file_content(owner, repo, path)
                if content is not None:
                    files.append({
                        "path": path,
                        "content": content,
                        "size_kb": round(size_kb, 1),
                    })

        return files

    def _parse_repo_url(self, url: str) -> tuple[str, str]:
        """Extrae owner/repo de una URL de GitHub."""
        parsed = urlparse(url)
        parts = parsed.path.strip("/").split("/")
        if len(parts) >= 2:
            return parts[0], parts[1].replace(".git", "")
        raise GitHubFetchError(f"URL inválida: {url}")

    def _get_repo_tree(self, owner: str, repo: str) -> list[dict]:
        """Obtiene el tree completo del repositorio (branch default)."""
        # Primero obtener la rama default
        repo_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"
        resp = self._session.get(repo_url)

        if resp.status_code == 404:
            raise GitHubFetchError(f"Repositorio no encontrado: {owner}/{repo}")
        if resp.status_code == 401:
            raise GitHubFetchError("Token de GitHub inválido o expirado")
        if resp.status_code == 403:
            raise GitHubFetchError("Acceso denegado. Verifica permisos del token.")
        if resp.status_code != 200:
            raise GitHubFetchError(f"Error GitHub API: {resp.status_code}")

        default_branch = resp.json().get("default_branch", "main")

        # Obtener tree recursivo
        tree_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1"
        resp = self._session.get(tree_url)

        if resp.status_code != 200:
            raise GitHubFetchError(f"Error obteniendo tree: {resp.status_code}")

        return resp.json().get("tree", [])

    def _get_file_content(self, owner: str, repo: str, path: str) -> str | None:
        """Descarga el contenido de un archivo específico."""
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
        resp = self._session.get(url)

        if resp.status_code != 200:
            return None

        data = resp.json()
        encoding = data.get("encoding", "")

        if encoding == "base64":
            try:
                content_b64 = data.get("content", "")
                return base64.b64decode(content_b64).decode("utf-8", errors="replace")
            except Exception:
                return None

        return data.get("content", "")

    def _get_extension(self, path: str) -> str:
        """Extrae la extensión de un path."""
        if '.' in path.split('/')[-1]:
            return '.' + path.rsplit('.', 1)[-1].lower()
        return ''
