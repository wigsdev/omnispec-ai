"""PRCreator — Cliente GitHub API para creación de Pull Requests.

Crea rama fix/omnispec-patch, aplica correcciones directamente
en los archivos afectados (no como .patch), y abre el PR.
Usa la GitHub Git Trees API para commitear múltiples archivos
en un solo commit atómico.
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

    Aplica correcciones directamente en los archivos del repo
    usando la Git Trees API (multi-file commit atómico).
    """

    def __init__(self, github_token: str | None = None):
        """Inicializa el PR creator."""
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
        fixed_files: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Crea rama con fixes aplicados y abre Pull Request.

        Args:
            repo_url: URL del repositorio.
            diff: Diff para mostrar en el PR body (preview).
            tests: Contenido de test_security_patch.py.
            findings: Hallazgos corregidos.
            fixed_files: Dict {path: contenido_corregido} para commit directo.

        Returns:
            Dict con 'pr_url', 'branch', 'files_changed'.
        """
        if not self._token:
            raise PRCreationError(
                "GITHUB_TOKEN no configurado. Conecta tu cuenta de GitHub."
            )

        owner, repo = self._parse_repo_url(repo_url)
        default_branch = self._get_default_branch(owner, repo)
        base_sha = self._get_branch_sha(owner, repo, default_branch)

        # Resolver nombre de rama
        branch_name = self._resolve_branch_name(owner, repo)

        # Crear rama
        self._create_branch(owner, repo, branch_name, base_sha)

        # Preparar archivos para commit
        files_to_commit: dict[str, str] = {}

        # Agregar archivos corregidos (si los tenemos)
        if fixed_files:
            files_to_commit.update(fixed_files)

        # Agregar test file
        if tests:
            files_to_commit["tests/test_security_patch.py"] = tests

        # Commit todos los archivos en un solo commit atómico
        commit_message = self._build_commit_message(findings)
        commit_sha = self._commit_tree(
            owner, repo, branch_name, base_sha,
            files_to_commit, commit_message
        )

        # Crear PR
        pr_body = self._build_pr_body(findings, diff, fixed_files)
        pr_url = self._open_pull_request(
            owner, repo, branch_name, default_branch,
            commit_message, pr_body
        )

        return {
            "pr_url": pr_url,
            "branch": branch_name,
            "commit_sha": commit_sha,
            "files_changed": len(files_to_commit),
        }

    def _commit_tree(
        self, owner: str, repo: str, branch: str,
        base_sha: str, files: dict[str, str], message: str
    ) -> str:
        """Commitea múltiples archivos usando Git Trees API (atómico).

        Crea blobs → tree → commit → update ref.
        """
        tree_items = []

        for path, content in files.items():
            # Crear blob para cada archivo
            blob_sha = self._create_blob(owner, repo, content)
            tree_items.append({
                "path": path,
                "mode": "100644",
                "type": "blob",
                "sha": blob_sha,
            })

        # Crear tree
        r = self._session.post(
            f"{GITHUB_API}/repos/{owner}/{repo}/git/trees",
            json={"base_tree": base_sha, "tree": tree_items}
        )
        if r.status_code not in (200, 201):
            raise PRCreationError(f"Error creando tree: {r.status_code}")
        tree_sha = r.json()["sha"]

        # Crear commit
        r = self._session.post(
            f"{GITHUB_API}/repos/{owner}/{repo}/git/commits",
            json={
                "message": message,
                "tree": tree_sha,
                "parents": [base_sha],
            }
        )
        if r.status_code not in (200, 201):
            raise PRCreationError(f"Error creando commit: {r.status_code}")
        commit_sha = r.json()["sha"]

        # Actualizar referencia de la rama
        r = self._session.patch(
            f"{GITHUB_API}/repos/{owner}/{repo}/git/refs/heads/{branch}",
            json={"sha": commit_sha}
        )
        if r.status_code not in (200, 201):
            raise PRCreationError(f"Error actualizando ref: {r.status_code}")

        return commit_sha

    def _create_blob(self, owner: str, repo: str, content: str) -> str:
        """Crea un blob en el repo."""
        r = self._session.post(
            f"{GITHUB_API}/repos/{owner}/{repo}/git/blobs",
            json={"content": content, "encoding": "utf-8"}
        )
        if r.status_code not in (200, 201):
            raise PRCreationError(f"Error creando blob: {r.status_code}")
        return r.json()["sha"]

    def _get_default_branch(self, owner: str, repo: str) -> str:
        """Obtiene la rama por defecto."""
        r = self._session.get(f"{GITHUB_API}/repos/{owner}/{repo}")
        if r.status_code == 403:
            raise InsufficientScopeError("Token sin scope 'repo'.")
        if r.status_code != 200:
            raise PRCreationError(f"Error accediendo repo: {r.status_code}")
        return r.json().get("default_branch", "main")

    def _get_branch_sha(self, owner: str, repo: str, branch: str) -> str:
        """Obtiene el SHA del HEAD."""
        r = self._session.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/git/ref/heads/{branch}"
        )
        if r.status_code != 200:
            raise PRCreationError(f"Rama '{branch}' no encontrada")
        return r.json()["object"]["sha"]

    def _resolve_branch_name(self, owner: str, repo: str) -> str:
        """Nombre de rama con timestamp fallback."""
        if self._branch_exists(owner, repo, self._base_branch_name):
            return f"{self._base_branch_name}-{int(time.time())}"
        return self._base_branch_name

    def _branch_exists(self, owner: str, repo: str, branch: str) -> bool:
        """Verifica si una rama existe."""
        r = self._session.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/git/ref/heads/{branch}"
        )
        return r.status_code == 200

    def _create_branch(self, owner: str, repo: str, branch: str, sha: str) -> None:
        """Crea una nueva rama."""
        r = self._session.post(
            f"{GITHUB_API}/repos/{owner}/{repo}/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": sha}
        )
        if r.status_code == 422:
            raise BranchExistsError(f"Rama '{branch}' ya existe")
        if r.status_code not in (200, 201):
            raise PRCreationError(f"Error creando rama: {r.status_code}")

    def _open_pull_request(
        self, owner: str, repo: str, branch: str,
        base: str, title: str, body: str
    ) -> str:
        """Abre un Pull Request."""
        r = self._session.post(
            f"{GITHUB_API}/repos/{owner}/{repo}/pulls",
            json={"title": title, "body": body, "head": branch, "base": base}
        )
        if r.status_code == 403:
            raise InsufficientScopeError("Token necesita scope 'repo'.")
        if r.status_code not in (200, 201):
            raise PRCreationError(f"Error creando PR: {r.status_code} {r.text[:200]}")
        return r.json().get("html_url", "")

    def _parse_repo_url(self, url: str) -> tuple[str, str]:
        """Extrae owner y repo de URL."""
        parts = url.rstrip('/').split('/')
        if len(parts) >= 2:
            return parts[-2], parts[-1]
        return "unknown", "unknown"

    def _build_commit_message(self, findings: list[dict[str, Any]]) -> str:
        """Commit message convencional."""
        if findings:
            count = len(findings)
            desc = findings[0].get('description', 'security vulnerability')
            if count > 1:
                return f"fix(security): remediate {count} security findings"
            return f"fix(security): {desc}"
        return "fix(security): remediate security findings"

    def _build_pr_body(
        self, findings: list[dict[str, Any]], diff: str,
        fixed_files: dict[str, str] | None = None
    ) -> str:
        """Construye el body del PR."""
        sections = [
            "## 🔒 Security Fix — OmniSpec AI\n",
            "### Hallazgos Corregidos\n"
        ]
        for f in findings:
            sections.append(
                f"- **[{f.get('severity', '?')}]** "
                f"{f.get('description', '?')} "
                f"(`{f.get('file', '?')}:{f.get('line', '?')}`)"
            )

        if fixed_files:
            sections.append(f"\n### Archivos Modificados ({len(fixed_files)})\n")
            for path in fixed_files:
                sections.append(f"- `{path}`")

        if diff:
            sections.append(f"\n### Diff Preview\n```diff\n{diff[:4000]}\n```")

        sections.append("\n---\n> 🤖 Generado por **OmniSpec AI** — Auto-Fix Engine")
        return "\n".join(sections)
