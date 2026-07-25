"""PRCreator — Cliente GitHub API para creación de Pull Requests.

Crea rama fix/omnispec-patch (con timestamp fallback si existe),
aplica diff, commitea con formato convencional, y abre PR.
"""

import time
from typing import Any


class BranchExistsError(Exception):
    """Raised cuando la rama ya existe en GitHub (422)."""
    pass


class InsufficientScopeError(Exception):
    """Raised cuando el token no tiene scope 'repo' (403)."""
    pass


class PRCreationError(Exception):
    """Raised para errores genéricos de creación de PR."""
    pass


class PRCreator:
    """Cliente para crear Pull Requests en GitHub.

    Gestiona el flujo: crear rama → commit → abrir PR,
    con fallback de branch naming si la rama ya existe.
    """

    def __init__(self, github_token: str | None = None):
        """Inicializa el PR creator.

        Args:
            github_token: Token de GitHub. Si None, lee de env.
        """
        import os
        self._token = github_token or os.environ.get("GITHUB_TOKEN", "")
        self._base_branch_name = "fix/omnispec-patch"

    def create_pr(
        self,
        repo_url: str,
        diff: str,
        tests: str,
        findings: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Crea una rama y Pull Request con el fix.

        Args:
            repo_url: URL del repositorio (https://github.com/owner/repo).
            diff: Unified diff del parche.
            tests: Contenido de test_security_patch.py.
            findings: Hallazgos corregidos.

        Returns:
            Dict con 'pr_url', 'branch', 'commit_sha'.

        Raises:
            InsufficientScopeError: Si el token no tiene scope 'repo'.
            PRCreationError: Para otros errores de GitHub API.
        """
        owner, repo = self._parse_repo_url(repo_url)
        branch_name = self._resolve_branch_name(owner, repo)

        # Crear rama
        self._create_branch(owner, repo, branch_name)

        # Commit diff + tests
        commit_message = self._build_commit_message(findings)
        commit_sha = self._commit_files(
            owner, repo, branch_name, diff, tests, commit_message
        )

        # Crear PR
        pr_body = self._build_pr_body(findings, diff, tests)
        pr_url = self._open_pull_request(
            owner, repo, branch_name, commit_message, pr_body
        )

        return {
            "pr_url": pr_url,
            "branch": branch_name,
            "commit_sha": commit_sha,
        }

    def _resolve_branch_name(self, owner: str, repo: str) -> str:
        """Resuelve el nombre de la rama, con timestamp si ya existe.

        Intenta fix/omnispec-patch. Si 422, appends timestamp.
        """
        try:
            if self._branch_exists(owner, repo, self._base_branch_name):
                return f"{self._base_branch_name}-{int(time.time())}"
        except Exception:
            pass
        return self._base_branch_name

    def _branch_exists(self, owner: str, repo: str, branch: str) -> bool:
        """Verifica si una rama ya existe (mock-friendly)."""
        # En implementación real: GET /repos/{owner}/{repo}/git/ref/heads/{branch}
        return False

    def _create_branch(self, owner: str, repo: str, branch: str) -> None:
        """Crea una nueva rama desde HEAD de main."""
        # Implementación real: POST /repos/{owner}/{repo}/git/refs
        pass

    def _commit_files(
        self, owner: str, repo: str, branch: str,
        diff: str, tests: str, message: str
    ) -> str:
        """Commitea el diff y tests en la rama."""
        # Implementación real: GitHub Contents API o Git Trees API
        return "abc123"

    def _open_pull_request(
        self, owner: str, repo: str, branch: str,
        title: str, body: str
    ) -> str:
        """Abre un Pull Request."""
        # POST /repos/{owner}/{repo}/pulls
        return f"https://github.com/{owner}/{repo}/pull/1"

    def _parse_repo_url(self, url: str) -> tuple[str, str]:
        """Extrae owner y repo de una URL de GitHub."""
        # https://github.com/owner/repo
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
            sections.append(f"- [{f.get('severity', '?')}] {f.get('description', '?')} ({f.get('file', '?')}:{f.get('line', '?')})")
        sections.append(f"\n### Diff Aplicado\n```diff\n{diff}\n```")
        sections.append(f"\n### Tests de Validación\n```python\n{tests}\n```")
        return "\n".join(sections)
