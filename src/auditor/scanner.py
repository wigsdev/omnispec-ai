"""AuditScanner — Orquestador principal de auditoría 3D.

Gestiona el flujo: file filtering → scan → score → explain.
Omite archivos > 256 KB y formatos no soportados [EDGE-2].

Attributes:
    MAX_FILE_SIZE_KB: Tamaño máximo de archivo para análisis (256 KB).
    SUPPORTED_EXTENSIONS: Extensiones de archivo soportadas.
    SPECIAL_FILENAMES: Nombres de archivo sin extensión que se analizan.
"""

from typing import Any

from src.auditor.structural import SecretsDetector, _is_test_file
from src.auditor.quality import IaCInspector
from src.auditor.compliance import GovernanceChecker
from src.auditor.report import ScoreCalculator

MAX_FILE_SIZE_KB = 256

# Extensiones organizadas por categoría para facilitar mantenimiento.
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({
    # --- Infraestructura y configuración original ---
    '.yaml', '.yml', '.json', '.tf', '.tfvars',
    '.template', '.cfg', '.toml', '.env',
    '.pem', '.key', '.sh',

    # --- Backend: lenguajes de servidor ---
    '.py',                              # Python
    '.js', '.mjs', '.cjs',             # JavaScript
    '.ts',                              # TypeScript
    '.jsx', '.tsx',                     # React
    '.java',                            # Java
    '.rb',                              # Ruby
    '.go',                              # Go
    '.php',                             # PHP
    '.cs',                              # C#
    '.rs',                              # Rust
    '.swift',                           # Swift (iOS/macOS)
    '.kt', '.kts',                      # Kotlin (Android / Gradle)
    '.scala',                           # Scala

    # --- Config de aplicaciones y entornos ---
    '.ini', '.conf', '.properties',     # Configs legacy
    '.config',                          # .NET / generic config
    '.xml',                             # Maven, Spring, Android
    '.gradle',                          # Gradle build scripts
    '.hcl',                             # Terraform HCL alternativo

    # --- CI/CD y DevOps ---
    '.npmrc',                           # Tokens de registro NPM
    '.dockerfile',                      # Dockerfile con extensión explícita
    '.env.local', '.env.development',   # Variantes dotenv subidas por error
    '.env.production', '.env.test',
    '.env.staging',
})

# Archivos sin extensión que contienen configuración o secretos con frecuencia.
# Se compara contra el nombre de archivo (basename), no la extensión.
SPECIAL_FILENAMES: frozenset[str] = frozenset({
    'Dockerfile',       # ARG/ENV con tokens
    'Makefile',         # Targets con credenciales hardcoded
    'Jenkinsfile',      # Pipeline CI con tokens
    'Podfile',          # iOS dependencies con tokens de repo privado
    'Gemfile',          # Ruby gems con source privado autenticado
    'Procfile',         # Heroku: puede exponer URIs con credenciales
    '.env',             # Dotenv sin extensión (raíz del repo)
    '.npmrc',           # NPM auth token (también como nombre sin extensión)
    '.gitconfig',       # Credenciales git embebidas
    '.htpasswd',        # Contraseñas Apache
    '.netrc',           # Credenciales FTP/HTTP
    'wp-config.php',    # WordPress DB credentials (nombre específico)
})


class AuditScanner:
    """Orquestador de auditoría tridimensional.

    Coordina los 3 inspectores (secrets, IaC, governance),
    calcula el score ponderado, y genera el reporte.
    """

    def __init__(self):
        """Inicializa los componentes del scanner."""
        self.secrets_detector = SecretsDetector()
        self.iac_inspector = IaCInspector()
        self.governance_checker = GovernanceChecker()
        self.score_calculator = ScoreCalculator()

    def scan(self, repo_url: str, files: list[dict] | None = None) -> dict[str, Any]:
        """Ejecuta auditoría completa sobre archivos de repositorio.

        Args:
            repo_url: URL del repositorio GitHub.
            files: Lista de archivos a analizar. Cada archivo es un dict
                   con keys: 'path', 'content', 'size_kb'.
                   Si None, retorna resultado vacío (EDGE-2).

        Returns:
            Dict con score, findings por categoría, y archivos omitidos.
        """
        if files is None:
            files = []

        # Filtrar archivos: size check + extension check
        analyzable, skipped = self._filter_files(files)

        # EDGE-2: repo vacío o sin archivos analizables
        if not analyzable:
            extensions_found = list({
                self._get_extension(f['path']) for f in files if f.get('path')
            })
            return {
                "score": None,
                "message": "N/A — Sin archivos analizables",
                "findings_count": 0,
                "findings": {"secrets": [], "iac": [], "governance": []},
                "skipped_files": skipped,
                "extensions_found": extensions_found,
            }

        # Ejecutar inspecciones
        # Enriquecer archivos con contexto de test antes de pasar al detector
        analyzable_with_context = [
            {**f, "is_test_file": _is_test_file(f.get("path", ""))}
            for f in analyzable
        ]
        secrets_findings = self.secrets_detector.scan(analyzable_with_context)
        iac_findings = self.iac_inspector.scan(analyzable)
        # Governance checks against ALL files (needs to see README, CHANGELOG, etc.)
        governance_findings = self.governance_checker.check(files)

        # Calcular score
        score = self.score_calculator.calculate(
            secrets_findings, iac_findings, governance_findings
        )

        all_findings = secrets_findings + iac_findings + governance_findings

        return {
            "score": score,
            "findings_count": len(all_findings),
            "findings": {
                "secrets": secrets_findings,
                "iac": iac_findings,
                "governance": governance_findings,
            },
            "skipped_files": skipped,
        }

    def _filter_files(
        self, files: list[dict]
    ) -> tuple[list[dict], list[dict]]:
        """Filtra archivos por tamaño y extensión/nombre.

        Acepta archivos cuya extensión esté en SUPPORTED_EXTENSIONS
        o cuyo nombre (basename) esté en SPECIAL_FILENAMES.

        Args:
            files: Lista completa de archivos.

        Returns:
            Tuple (analyzable, skipped).
        """
        analyzable = []
        skipped = []

        for f in files:
            path = f.get('path', '')
            size_kb = f.get('size_kb', 0)
            ext = self._get_extension(path)
            basename = self._get_basename(path)

            if size_kb > MAX_FILE_SIZE_KB:
                skipped.append({
                    "path": path,
                    "size_kb": size_kb,
                    "reason": f"exceeds_{MAX_FILE_SIZE_KB}kb_limit",
                })
            elif ext in SUPPORTED_EXTENSIONS or basename in SPECIAL_FILENAMES:
                analyzable.append(f)
            else:
                skipped.append({
                    "path": path,
                    "size_kb": size_kb,
                    "reason": f"unsupported_extension: {ext}",
                })

        return analyzable, skipped

    def _get_basename(self, path: str) -> str:
        """Extrae el nombre de archivo (sin directorio) de un path."""
        # Soporta tanto '/' como '\\' como separadores
        return path.replace('\\', '/').rsplit('/', 1)[-1]

    def _get_extension(self, path: str) -> str:
        """Extrae la extensión de un path de archivo.

        Soporta extensiones compuestas tipo '.env.local'.
        Retorna '' si el archivo no tiene extensión.
        """
        basename = self._get_basename(path)
        # Extensión compuesta: .env.local, .env.production, etc.
        if basename.count('.') >= 2:
            parts = basename.split('.', 1)
            compound = '.' + parts[1]  # e.g. '.env.local'
            if compound in SUPPORTED_EXTENSIONS:
                return compound
        if '.' in basename:
            return '.' + basename.rsplit('.', 1)[-1].lower()
        return ''
