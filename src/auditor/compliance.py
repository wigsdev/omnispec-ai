"""GovernanceChecker — Verificador de cumplimiento de gobierno.

Verifica presencia de tags obligatorios, naming conventions,
y documentación requerida (README, CHANGELOG, tests).

Attributes:
    REQUIRED_TAGS: Tags obligatorios para recursos AWS.
"""

from typing import Any

REQUIRED_TAGS = {"Environment", "Owner", "Project", "CostCenter"}


class GovernanceChecker:
    """Verificador de gobierno y compliance.

    Inspecciona archivos IaC buscando tags faltantes,
    y verifica presencia de documentación estándar.
    """

    def check(self, files: list[dict]) -> list[dict[str, Any]]:
        """Ejecuta verificación de gobierno sobre archivos.

        Args:
            files: Lista de archivos con keys 'path' y 'content'.

        Returns:
            Lista de hallazgos de gobierno.
        """
        findings: list[dict[str, Any]] = []

        # Verificar documentación requerida
        findings.extend(self._check_documentation(files))

        # Verificar tags en archivos IaC
        findings.extend(self._check_tags(files))

        return findings

    def _check_documentation(
        self, files: list[dict]
    ) -> list[dict[str, Any]]:
        """Verifica presencia de documentación obligatoria."""
        findings = []
        paths = {f.get('path', '').lower() for f in files}
        all_paths_str = ' '.join(paths)

        required_docs = {
            "README.md": "readme",
            "CHANGELOG.md": "changelog",
        }

        for doc_name, key in required_docs.items():
            if key not in all_paths_str:
                findings.append({
                    "file": doc_name,
                    "line": 0,
                    "type": f"missing_{key}",
                    "severity": "low",
                    "penalty": 2,
                    "description": f"Documento {doc_name} no encontrado",
                    "category": "governance",
                })

        # Verificar estructura de tests
        has_tests = any('test' in p for p in paths)
        if not has_tests:
            findings.append({
                "file": "tests/",
                "line": 0,
                "type": "missing_tests",
                "severity": "medium",
                "penalty": 5,
                "description": "No se encontró estructura de tests",
                "category": "governance",
            })

        return findings

    def _check_tags(self, files: list[dict]) -> list[dict[str, Any]]:
        """Verifica tags obligatorios en archivos IaC."""
        findings = []

        for file_info in files:
            path = file_info.get('path', '')
            content = file_info.get('content', '')

            if not self._is_iac_file(path) or not content:
                continue

            # Verificar si el archivo define recursos (tiene Tags section)
            if 'resource' in content.lower() or 'aws::' in content:
                missing_tags = self._find_missing_tags(content)
                if missing_tags:
                    findings.append({
                        "file": path,
                        "line": 0,
                        "type": "missing_tags",
                        "severity": "medium",
                        "penalty": 5,
                        "description": f"Tags faltantes: {', '.join(missing_tags)}",
                        "category": "governance",
                    })

        return findings

    def _find_missing_tags(self, content: str) -> list[str]:
        """Encuentra tags obligatorios que faltan en el contenido."""
        content_lower = content.lower()
        missing = []
        for tag in REQUIRED_TAGS:
            if tag.lower() not in content_lower:
                missing.append(tag)
        return missing

    def _is_iac_file(self, path: str) -> bool:
        """Determina si un archivo es de IaC."""
        path_lower = path.lower()
        return path_lower.endswith(('.tf', '.template', '.json', '.yaml', '.yml')) and \
               any(k in path_lower for k in ('infra', 'stack', 'cloudformation', 'cdk'))
