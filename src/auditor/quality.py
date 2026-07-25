"""IaCInspector — Inspector de seguridad Infrastructure-as-Code.

Analiza archivos CloudFormation/CDK/Terraform detectando:
- Políticas IAM con Action: "*" o Resource: "*"
- Security Groups con ingress 0.0.0.0/0 en puertos sensibles

Soporta formatos JSON y YAML.
"""

import re
from typing import Any

# Puertos sensibles que no deben estar abiertos a 0.0.0.0/0
SENSITIVE_PORTS = {22, 3389, 3306, 5432, 27017, 6379}

# Patterns para IAM wildcards (JSON y YAML)
IAM_ACTION_WILDCARD = re.compile(
    r"""["']?Action["']?\s*:\s*["']\*["']""",
    re.IGNORECASE
)
IAM_ACTION_WILDCARD_LIST = re.compile(
    r"""["']?Action["']?\s*:\s*\[\s*["']\*["']\s*\]""",
    re.IGNORECASE
)
IAM_RESOURCE_WILDCARD = re.compile(
    r"""["']?Resource["']?\s*:\s*["']\*["']""",
    re.IGNORECASE
)

# Pattern para Security Groups abiertos
SG_OPEN_CIDR = re.compile(
    r"""(?:CidrIp|cidr_blocks?)\s*[=:]\s*\[?\s*["']?0\.0\.0\.0/0["']?""",
    re.IGNORECASE
)

# Pattern para detectar puertos en contexto cercano
PORT_PATTERN = re.compile(
    r"""(?:FromPort|from_port|ingress.*port)\s*[=:]\s*(\d+)""",
    re.IGNORECASE
)


class IaCInspector:
    """Inspector de seguridad para Infrastructure-as-Code.

    Detecta configuraciones inseguras en CloudFormation, CDK y Terraform.
    """

    def scan(self, files: list[dict]) -> list[dict[str, Any]]:
        """Escanea archivos IaC buscando configuraciones inseguras.

        Args:
            files: Lista de archivos con keys 'path' y 'content'.

        Returns:
            Lista de hallazgos IaC.
        """
        findings: list[dict[str, Any]] = []

        for file_info in files:
            path = file_info.get('path', '')
            content = file_info.get('content', '')

            if not content:
                continue

            # Solo inspeccionar archivos IaC
            if not self._is_iac_file(path):
                continue

            findings.extend(self._check_iam_wildcards(path, content))
            findings.extend(self._check_open_security_groups(path, content))

        return findings

    def _is_iac_file(self, path: str) -> bool:
        """Determina si un archivo es de IaC."""
        path_lower = path.lower()
        # .tf files are always IaC
        if path_lower.endswith('.tf'):
            return True
        iac_indicators = (
            '.template', 'cloudformation',
            'cdk.json', 'stack', 'infra',
        )
        if path_lower.endswith(('.json', '.yaml', '.yml')):
            return any(ind in path_lower for ind in iac_indicators)
        return False

    def _check_iam_wildcards(
        self, path: str, content: str
    ) -> list[dict[str, Any]]:
        """Detecta políticas IAM con wildcards."""
        findings = []
        lines = content.split('\n')

        for line_num, line in enumerate(lines, start=1):
            if IAM_ACTION_WILDCARD.search(line) or IAM_ACTION_WILDCARD_LIST.search(line):
                findings.append({
                    "file": path,
                    "line": line_num,
                    "type": "iam_action_wildcard",
                    "severity": "high",
                    "penalty": 10,
                    "description": "Política IAM con Action: \"*\" — acceso total",
                    "reference": "CIS AWS 1.16, Well-Architected SEC03",
                    "category": "iac",
                })
            if IAM_RESOURCE_WILDCARD.search(line):
                findings.append({
                    "file": path,
                    "line": line_num,
                    "type": "iam_resource_wildcard",
                    "severity": "high",
                    "penalty": 10,
                    "description": "Política IAM con Resource: \"*\" — scope ilimitado",
                    "reference": "CIS AWS 1.16, Well-Architected SEC03",
                    "category": "iac",
                })

        return findings

    def _check_open_security_groups(
        self, path: str, content: str
    ) -> list[dict[str, Any]]:
        """Detecta Security Groups abiertos en puertos sensibles."""
        findings = []
        lines = content.split('\n')

        for line_num, line in enumerate(lines, start=1):
            if SG_OPEN_CIDR.search(line):
                # Buscar puerto en contexto (5 líneas antes y después)
                context_start = max(0, line_num - 6)
                context_end = min(len(lines), line_num + 5)
                context = '\n'.join(lines[context_start:context_end])

                port_match = PORT_PATTERN.search(context)
                port = int(port_match.group(1)) if port_match else None

                if port is None or port in SENSITIVE_PORTS:
                    findings.append({
                        "file": path,
                        "line": line_num,
                        "type": "open_security_group",
                        "severity": "high",
                        "penalty": 10,
                        "description": f"Security Group abierto (0.0.0.0/0)"
                                       f"{f' en puerto {port}' if port else ''}",
                        "reference": "CIS AWS 4.1-4.3, Well-Architected SEC05",
                        "category": "iac",
                    })

        return findings
