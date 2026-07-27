"""SecretsDetector — Detector estático de secretos expuestos.

Escanea archivos buscando patrones de secretos usando regex
non-greedy (prevención de ReDoS). No almacena valores de secretos,
solo metadata (archivo, línea, tipo, severidad).

Aplica lógica contextual para reducir falsos positivos:
- Valores en KNOWN_SAFE_VALUES se ignoran (ejemplos de documentación oficial).
- Matches con sufijos de prueba conocidos se degradan a severidad 'info'.
- Archivos en rutas de test (tests/, spec/) se degradan a severidad 'info'.

Attributes:
    SECRET_PATTERNS: Dict de patrones regex por tipo de secreto.
    KNOWN_SAFE_VALUES: Set de strings que son ejemplos conocidos seguros.
    TEST_PATH_SEGMENTS: Segmentos de path que identifican archivos de test.
    SAFE_VALUE_SUFFIXES: Sufijos que indican que un valor es de prueba.
"""

import re
from typing import Any

# Regex non-greedy para prevenir ReDoS (recomendación del Review)
SECRET_PATTERNS = {
    # ------------------------------------------------------------------ #
    # Patrones originales                                                  #
    # ------------------------------------------------------------------ #
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

    # ------------------------------------------------------------------ #
    # Connection strings con credenciales embebidas                        #
    # ------------------------------------------------------------------ #
    "connection_string_db": {
        "regex": re.compile(
            r"""(?:jdbc|mongodb(?:\+srv)?|postgresql|mysql|mssql|redis|amqp)"""
            r"""://[^:@\s]{1,100}:[^@\s]{1,200}@[^\s'"]{1,300}""",
            re.IGNORECASE
        ),
        "severity": "critical",
        "penalty": 20,
        "description": "Connection string con credenciales embebidas",
    },

    # ------------------------------------------------------------------ #
    # API keys genéricas en asignaciones y JSON/YAML                       #
    # ------------------------------------------------------------------ #
    "generic_api_key": {
        "regex": re.compile(
            r"""(?:api[_\-]?key|apikey|x[_\-]api[_\-]key|access[_\-]?key)"""
            r"""[\s"'\]]*[=:]\s*['"]?[A-Za-z0-9\-._]{20,}['"]?""",
            re.IGNORECASE
        ),
        "severity": "high",
        "penalty": 15,
        "description": "API key genérica expuesta",
    },
    "generic_secret": {
        "regex": re.compile(
            r"""(?:secret[_\-]?key|client[_\-]?secret|app[_\-]?secret)"""
            r"""\s*[=:]\s*['"][^'"]{8,200}['"]""",
            re.IGNORECASE
        ),
        "severity": "high",
        "penalty": 15,
        "description": "Secret key genérico expuesto",
    },

    # ------------------------------------------------------------------ #
    # Tokens de plataformas y CI/CD                                        #
    # ------------------------------------------------------------------ #
    "github_token": {
        "regex": re.compile(
            r"""(?:gh[pousr]|github_pat)_[A-Za-z0-9_]{30,}""",
            re.IGNORECASE
        ),
        "severity": "critical",
        "penalty": 20,
        "description": "GitHub Personal Access Token expuesto",
    },
    "slack_token": {
        "regex": re.compile(
            r"""xox[bpars]-[0-9A-Za-z\-]{10,}"""
        ),
        "severity": "critical",
        "penalty": 20,
        "description": "Slack token expuesto",
    },
    "stripe_key": {
        "regex": re.compile(
            r"""(?:sk|rk)_(?:live|test)_[0-9A-Za-z]{20,}"""
        ),
        "severity": "critical",
        "penalty": 20,
        "description": "Stripe secret key expuesta",
    },
    "ci_token_hardcoded": {
        "regex": re.compile(
            r"""(?:CIRCLE_TOKEN|TRAVIS_TOKEN|CI_TOKEN|JENKINS_TOKEN|SONAR_TOKEN)"""
            r"""\s*[=:]\s*['"]?[A-Za-z0-9\-_]{10,}['"]?""",
            re.IGNORECASE
        ),
        "severity": "high",
        "penalty": 15,
        "description": "Token de CI/CD hardcoded",
    },

    # ------------------------------------------------------------------ #
    # Google Cloud / Service Account                                       #
    # ------------------------------------------------------------------ #
    "google_service_account": {
        "regex": re.compile(
            r""""type"\s*:\s*"service_account\""""
        ),
        "severity": "critical",
        "penalty": 20,
        "description": "Google Service Account key file detectado",
    },
    "google_api_key": {
        "regex": re.compile(
            r"""AIza[0-9A-Za-z\-_]{35}"""
        ),
        "severity": "critical",
        "penalty": 20,
        "description": "Google API Key expuesta",
    },

    # ------------------------------------------------------------------ #
    # NPM y registros de paquetes                                          #
    # ------------------------------------------------------------------ #
    "npm_auth_token": {
        "regex": re.compile(
            r"""(?://[^:]+:)?_authToken\s*=\s*[A-Za-z0-9\-_]{20,}""",
            re.IGNORECASE
        ),
        "severity": "critical",
        "penalty": 20,
        "description": "NPM auth token expuesto en .npmrc",
    },
}

# Valores de ejemplo bien documentados por AWS y la industria.
# Cualquier match exacto con estas strings se descarta — no es un secreto real.
KNOWN_SAFE_VALUES: frozenset[str] = frozenset({
    "AKIAIOSFODNN7EXAMPLE",      # Ejemplo canónico de la documentación oficial AWS
    "AKID1234567890EXAMPLE",     # Variante de ejemplo AWS
    "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",  # Secret key de ejemplo AWS docs
    "your-access-key-id",
    "your-secret-access-key",
    "YOUR_ACCESS_KEY",
    "YOUR_SECRET_KEY",
    "INSERT_KEY_HERE",
    "YOUR_KEY_HERE",
    "REPLACE_ME",
    "CHANGE_ME",
    "YOUR_API_KEY",
    "YOUR_TOKEN_HERE",
})

# Sufijos (case-insensitive) que indican que el valor es de prueba intencional.
SAFE_VALUE_SUFFIXES: tuple[str, ...] = (
    "example",
    "placeholder",
    "_test",
    "_fake",
    "_dummy",
    "_mock",
    "_sample",
    "_fixture",
    "_stub",
)

# Segmentos de path que identifican archivos de test.
TEST_PATH_SEGMENTS: tuple[str, ...] = (
    "tests/",
    "test/",
    "spec/",
    "/test_",
    "\\test_",
    "_test.py",
    "_spec.py",
)


def _is_test_file(path: str) -> bool:
    """Determina si un path corresponde a un archivo de test.

    Args:
        path: Path del archivo a evaluar.

    Returns:
        True si el path pertenece a un directorio o archivo de test.
    """
    path_lower = path.lower()
    return any(segment in path_lower for segment in TEST_PATH_SEGMENTS)


def _matched_value_looks_like_example(match: re.Match) -> bool:
    """Evalúa si el valor matcheado parece un ejemplo de documentación o prueba.

    Comprueba contra KNOWN_SAFE_VALUES (exacto) y SAFE_VALUE_SUFFIXES
    usando el texto completo del match.

    Un valor que parece ejemplo en código de producción → severidad 'low'.
    Un valor que parece ejemplo en contexto de test → descartado.

    Args:
        match: El objeto re.Match del patrón encontrado.

    Returns:
        True si el valor parece un ejemplo o placeholder intencional.
    """
    raw_value = match.group(0)
    value_upper = raw_value.upper()

    # Verificar allowlist exacta (case-sensitive para AWS keys)
    if raw_value in KNOWN_SAFE_VALUES:
        return True

    # Verificar sufijos de prueba (case-insensitive)
    return any(value_upper.endswith(suffix.upper()) for suffix in SAFE_VALUE_SUFFIXES)


class SecretsDetector:
    """Detector de secretos expuestos en archivos de código.

    Escanea usando regex non-greedy y retorna solo metadata
    (nunca el valor del secreto). AC-2.2.3 compliant.

    Aplica reducción de falsos positivos mediante contexto de path
    y allowlist de valores conocidos como seguros.
    """

    def scan(self, files: list[dict]) -> list[dict[str, Any]]:
        """Escanea archivos buscando secretos expuestos.

        Aplica lógica contextual para clasificar hallazgos:

        +------------------+--------------+-----------------------------+
        | Contexto         | Valor ejemplo| Resultado                   |
        +==================+==============+=============================+
        | Producción       | No           | severity=critical penalty=20|
        | Producción       | Sí           | severity=low     penalty=2  |
        | Test             | No           | severity=info    penalty=0  |
        | Test             | Sí           | Descartado (falso positivo) |
        +------------------+--------------+-----------------------------+

        Args:
            files: Lista de archivos con keys 'path', 'content',
                   y opcionalmente 'is_test_file' (bool).

        Returns:
            Lista de hallazgos con metadata (sin valores de secretos).
        """
        findings: list[dict[str, Any]] = []

        for file_info in files:
            path = file_info.get('path', '')
            content = file_info.get('content', '')

            if not content:
                continue

            # El scanner puede inyectar is_test_file; si no, lo inferimos.
            in_test_context = file_info.get('is_test_file', _is_test_file(path))

            lines = content.split('\n')
            for line_num, line in enumerate(lines, start=1):
                for secret_type, pattern_info in SECRET_PATTERNS.items():
                    match = pattern_info["regex"].search(line)
                    if not match:
                        continue

                    looks_like_example = _matched_value_looks_like_example(match)

                    # Test + valor ejemplo → falso positivo, descartar
                    if in_test_context and looks_like_example:
                        continue

                    # Determinar severidad y penalty según contexto
                    if in_test_context:
                        # Secreto real en archivo de test → notificar sin penalizar
                        severity = "info"
                        penalty = 0
                    elif looks_like_example:
                        # Valor de ejemplo en producción → sospechoso pero bajo riesgo
                        severity = "low"
                        penalty = 2
                    else:
                        severity = pattern_info["severity"]
                        penalty = pattern_info["penalty"]

                    findings.append({
                        "file": path,
                        "line": line_num,
                        "type": secret_type,
                        "severity": severity,
                        "penalty": penalty,
                        "description": pattern_info["description"],
                        "category": "secrets",
                        "in_test_file": in_test_context,
                    })

        return findings
