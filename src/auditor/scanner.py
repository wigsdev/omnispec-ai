"""AuditScanner — Orquestador principal de auditoría 3D.

Gestiona el flujo: file filtering → scan → score → explain.
Omite archivos > 256 KB y formatos no soportados [EDGE-2].

Attributes:
    MAX_FILE_SIZE_KB: Tamaño máximo de archivo para análisis (256 KB).
    SUPPORTED_EXTENSIONS: Extensiones de archivo soportadas.
"""

from typing import Any

from src.auditor.structural import SecretsDetector
from src.auditor.quality import IaCInspector
from src.auditor.compliance import GovernanceChecker
from src.auditor.report import ScoreCalculator

MAX_FILE_SIZE_KB = 256
SUPPORTED_EXTENSIONS = {
    '.py', '.yaml', '.yml', '.json', '.tf',
    '.template', '.cfg', '.toml', '.env',
    '.pem', '.key', '.sh',
}


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
        secrets_findings = self.secrets_detector.scan(analyzable)
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
        """Filtra archivos por tamaño y extensión.

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

            if size_kb > MAX_FILE_SIZE_KB:
                skipped.append({
                    "path": path,
                    "size_kb": size_kb,
                    "reason": f"exceeds_{MAX_FILE_SIZE_KB}kb_limit",
                })
            elif ext not in SUPPORTED_EXTENSIONS:
                skipped.append({
                    "path": path,
                    "size_kb": size_kb,
                    "reason": f"unsupported_extension: {ext}",
                })
            else:
                analyzable.append(f)

        return analyzable, skipped

    def _get_extension(self, path: str) -> str:
        """Extrae la extensión de un path de archivo."""
        if '.' in path:
            return '.' + path.rsplit('.', 1)[-1].lower()
        return ''
