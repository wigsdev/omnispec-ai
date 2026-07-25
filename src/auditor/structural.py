"""SecretsDetector — Detector estático de secretos expuestos.

Escanea archivos buscando patrones de secretos usando regex
non-greedy (prevención de ReDoS). No almacena valores de secretos,
solo metadata (archivo, línea, tipo, severidad).

Attributes:
    SECRET_PATTERNS: Dict de patrones regex por tipo de secreto.
"""

import re
from typing import Any

# Regex non-greedy para prevenir ReDoS (recomendación del Review)
SECRET_PATTERNS = {
    "aws_access_key": {
        "regex": re.compile(r"AKIA[0-9A-Z]{16}"),
        "severity": "critical",
        "penalty": 20,
        "description": "AWS Access Key expuesta",
    },
    "password_assignment": {
        "regex": re.compile(
            r"""(?:password|passwd|pwd)\s*[=:]\s*['"][^'"]{1,200}['"]""",
            re.IGNORECASE
        ),
        "severity": "critical",
        "penalty": 20,
        "description": "Password hardcoded en código",
    },
    "bearer_token": {
        "regex": re.compile(
            r"""(?:Bearer|Authorization)\s+[A-Za-z0-9\-._~+/]{20,}={0,2}""",
            re.IGNORECASE
        ),
        "severity": "critical",
        "penalty": 20,
        "description": "Token Bearer/JWT expuesto",
    },
    "private_key": {
        "regex": re.compile(
            r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----"
        ),
        "severity": "critical",
        "penalty": 20,
        "description": "Clave privada PEM expuesta",
    },
}


class SecretsDetector:
    """Detector de secretos expuestos en archivos de código.

    Escanea usando regex non-greedy y retorna solo metadata
    (nunca el valor del secreto). AC-2.2.3 compliant.
    """

    def scan(self, files: list[dict]) -> list[dict[str, Any]]:
        """Escanea archivos buscando secretos expuestos.

        Args:
            files: Lista de archivos con keys 'path' y 'content'.

        Returns:
            Lista de hallazgos con metadata (sin valores de secretos).
        """
        findings: list[dict[str, Any]] = []

        for file_info in files:
            path = file_info.get('path', '')
            content = file_info.get('content', '')

            if not content:
                continue

            lines = content.split('\n')
            for line_num, line in enumerate(lines, start=1):
                for secret_type, pattern_info in SECRET_PATTERNS.items():
                    if pattern_info["regex"].search(line):
                        findings.append({
                            "file": path,
                            "line": line_num,
                            "type": secret_type,
                            "severity": pattern_info["severity"],
                            "penalty": pattern_info["penalty"],
                            "description": pattern_info["description"],
                            "category": "secrets",
                        })

        return findings
