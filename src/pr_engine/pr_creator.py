"""PRCreator — Cliente GitHub API para creación de Pull Requests.

Crea rama fix/omnispec-patch (con timestamp fallback si existe),
aplica archivos con fix, commitea y abre PR via GitHub REST API v3.
"""

import base64
import os
import time
from typing import Any

import requests


class BranchExistsError(Exception):
    """Raised cuando la rama ya existe en GitHub (422)."""
    pass


class InsufficientScopeError(Exception):
    """Raised cuando el token no tiene scope 'repo' (403)."""
    pass


class PRCreationError(Exception):
    """Raised para errores genéricos de creación de PR."""
    pass


GITHUB_API = "https://api.github.com"


class PRCreator:
    """Cliente para crear Pull Requests en GitHub.

    Gestiona el flujo: crear rama → commit archivos → abrir PR,
    con fallback de branch naming si la rama ya existe.
    """

    def __init__(self, github_token: str | None = None):
        """Inicializa el PR creator.

        Args:
            github_token: Token de GitHub. Si None, lee de env.
        """
        self._token = github_token or os.environ.get("GITHUB_TOKEN", "")
        self._base_branch_name = "fix/omnispec-patch"
        self._session = requests.Session()
        if self._token:
            self._session.headers["Authorization"] = f"Bearer {self._token}"
        self._session.headers["Accept"] = "application/vnd.github.v3+json"
        self._session.headers["User-Agent"] = "OmniSpec-AI/1.0"

    def create_pr(
        self,
        repo_url: str,
        diff: str,
        tests: str,
        findings: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Crea una rama y Pull Request con el fix.

        Args:
            repo_url: URL del repositorio.
            diff: Unified diff del parche.
            tests: Contenido de test_security_patch.py.
            findings: Hallazgos corregidos.

        Returns:
            Dict con 'pr_url', 'branch', 'commit_sha'.
        """
        if not self._token:
            raise PRCreationError(
                "GITHUB_TOKEN no configurado. Agrega tu token en .env"
            )

        owner, repo = self._parse_repo_url(repo_url)

        # Obtener SHA de la rama principal
        default_branch = self._get_default_branch(owner, repo)
        base_sha = self._get_branch_sha(owner, repo, default_branch)

        # Resolver nombre de rama
        branch_name = self._resolve_branch_name(owner, repo)

        # Crear rama
        self._create_branch(owner, repo, branch_name, base_sha)

        # Commit archivos (diff como archivo .patch + tests)
        commit_message = self._build_commit_message(findings)
        commit_sha = self._commit_files(
            owner, repo, branch_name,
            diff, tests, commit_message
        )

        # Crear PR
        pr_body = self._build_pr_body(findings, diff, tests)
        pr_url = self._open_pull_request(
            owner, repo, branch_name, default_branch,
            commit_message, pr_body
        )

        return {
            "pr_url": pr_url,
            "branch": branch_name,
            "commit_sha": commit_sha,
        }

    def _get_default_branch(self, owner: str, repo: str) -> str:
        """Obtiene la rama por defecto del repo."""
        r = self._session.get(f"{GITHUB_API}/repos/{owner}/{repo}")
        if r.status_code == 403:
            raise InsufficientScopeError(
                "Token sin permisos. Necesita scope 'repo'."
            )
        if r.status_code != 200:
            raise PRCreationError(f"Error accediendo repo: {r.status_code}")
        return r.json().get("default_branch", "main")

    def _get_branch_sha(self, owner: str, repo: str, branch: str) -> str:
        """Obtiene el SHA del HEAD de una rama."""
        r = self._session.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/git/ref/heads/{branch}"
        )
        if r.status_code != 200:
            raise PRCreationError(f"Rama '{branch}' no encontrada")
        return r.json()["object"]["sha"]

    def _resolve_branch_name(self, owner: str, repo: str) -> str:
        """Resuelve nombre de rama con timestamp si ya existe."""
        if self._branch_exists(owner, repo, self._base_branch_name):
            return f"{self._base_branch_name}-{int(time.time())}"
        return self._base_branch_name

    def _branch_exists(self, owner: str, repo: str, branch: str) -> bool:
        """Verifica si una rama existe."""
        r = self._session.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/git/ref/heads/{branch}"
        )
        return r.status_code == 200

    def _create_branch(
        self, owner: str, repo: str, branch: str, sha: str
    ) -> None:
        """Crea una nueva rama desde un SHA."""
        r = self._session.post(
            f"{GITHUB_API}/repos/{owner}/{repo}/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": sha}
        )
        if r.status_code == 422:
            raise BranchExistsError(f"Rama '{branch}' ya existe")
        if r.status_code not in (200, 201):
            raise PRCreationError(
                f"Error creando rama: {r.status_code} {r.text[:200]}"
            )

    def _commit_files(
        self, owner: str, repo: str, branch: str,
        diff: str, tests: str, message: str
    ) -> str:
        """Commitea archivos en la rama via Contents API."""
        # Subir test_security_patch.py
        self._put_file(
            owner, repo, branch,
            "tests/test_security_patch.py",
            tests, message
        )

        # Subir el diff como archivo .patch
        sha = self._put_file(
            owner, repo, branch,
            "omnispec-fix.patch",
            diff, message
        )

        return sha

    def _put_file(
        self, owner: str, repo: str, branch: str,
        path: str, content: str, message: str
    ) -> str:
        """Sube o actualiza un archivo via Contents API."""
        encoded = base64.b64encode(content.encode()).decode()

        # Check if file exists (para obtener sha si update)
        existing_sha = None
        r = self._session.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}",
            params={"ref": branch}
        )
        if r.status_code == 200:
            existing_sha = r.json().get("sha")

        payload = {
            "message": message,
            "content": encoded,
            "branch": branch,
        }
        if existing_sha:
            payload["sha"] = existing_sha

        r = self._session.put(
            f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}",
            json=payload
        )
        if r.status_code not in (200, 201):
            raise PRCreationError(
                f"Error subiendo {path}: {r.status_code} {r.text[:200]}"
            )
        return r.json().get("commit", {}).get("sha", "")

    def _open_pull_request(
        self, owner: str, repo: str, branch: str,
        base: str, title: str, body: str
    ) -> str:
        """Abre un Pull Request."""
        r = self._session.post(
            f"{GITHUB_API}/repos/{owner}/{repo}/pulls",
            json={
                "title": title,
                "body": body,
                "head": branch,
                "base": base,
            }
        )
        if r.status_code == 403:
            raise InsufficientScopeError(
                "Token necesita scope 'repo' para crear PRs."
            )
        if r.status_code not in (200, 201):
            raise PRCreationError(
                f"Error creando PR: {r.status_code} {r.text[:200]}"
            )
        return r.json().get("html_url", "")

    def _parse_repo_url(self, url: str) -> tuple[str, str]:
        """Extrae owner y repo de una URL de GitHub."""
        parts = url.rstrip('/').split('/')
        if len(parts) >= 2:
            return parts[-2], parts[-1]
        return "unknown", "unknown"

    def _build_commit_message(self, findings: list[dict[str, Any]]) -> str:
        """Construye el commit message en formato convencional."""
        if findings:
            desc = findings[0].get('description', 'security vulnerability')
            return f"fix(security): {desc}"
        return "fix(security): remediate security findings"

    def _build_pr_body(
        self, findings: list[dict[str, Any]], diff: str, tests: str
    ) -> str:
        """Construye el body del Pull Request."""
        sections = ["## Security Fix — OmniSpec AI\n"]
        sections.append("### Hallazgos Corregidos\n")
        for f in findings:
            sections.append(
                f"- **[{f.get('severity', '?')}]** "
                f"{f.get('description', '?')} "
                f"(`{f.get('file', '?')}:{f.get('line', '?')}`)"
            )
        sections.append(f"\n### Diff Aplicado\n```diff\n{diff[:3000]}\n```")
        sections.append(f"\n### Tests de Validación\n```python\n{tests[:2000]}\n```")
        sections.append("\n---\n> Generado por OmniSpec AI — Auto-Fix Engine")
        return "\n".join(sections)
