"""Auditor Routes — Endpoints de Auditoría 3D (US-2).

Endpoints:
    POST /api/v1/audit            — Inicia auditoría 3D (JSON response)
    GET  /api/v1/audit/stream     — Auditoría progresiva via SSE
    GET  /api/v1/audit/<id>/status — Estado de auditoría
    GET  /api/v1/audit/<id>/report — Reporte completo
"""

import json
import time
import uuid

from flask import Blueprint, Response, jsonify, request, stream_with_context

from src.auditor.scanner import AuditScanner
from src.auditor.structural import SecretsDetector
from src.auditor.quality import IaCInspector
from src.auditor.compliance import GovernanceChecker
from src.auditor.report import ScoreCalculator

auditor_bp = Blueprint('auditor', __name__)

# Almacén en memoria de auditorías (dev/test)
_audits: dict = {}


@auditor_bp.route('/api/v1/audit', methods=['POST'])
def start_audit():
    """Inicia una auditoría 3D de un repositorio GitHub.

    Protocolo Human-in-the-Loop: Si permission_granted != true,
    retorna 200 con status "cancelled" sin llamar a GitHub API.
    """
    data = request.get_json(silent=True)
    if not data or not data.get('repo_url'):
        return jsonify({
            "error": "bad_request",
            "message": "El campo 'repo_url' es requerido"
        }), 400

    repo_url = data['repo_url'].strip()
    permission_granted = data.get('permission_granted', False)

    if not permission_granted:
        audit_id = str(uuid.uuid4())
        _audits[audit_id] = {
            "id": audit_id,
            "status": "cancelled",
            "repo_url": repo_url,
            "permission_granted": False,
            "timestamp": time.time(),
        }
        return jsonify({
            "id": audit_id,
            "status": "cancelled",
            "message": "Auditoría cancelada por el usuario",
            "permission_granted": False,
        }), 200

    # Permission granted — auditoría completa
    audit_id = str(uuid.uuid4())
    scanner = AuditScanner()

    try:
        from src.auditor.github_fetcher import GitHubFetcher, GitHubFetchError
        fetcher = GitHubFetcher()
        try:
            files = fetcher.fetch_repo_files(repo_url)
        except GitHubFetchError as e:
            _audits[audit_id] = {
                "id": audit_id, "status": "error",
                "repo_url": repo_url, "error": str(e), "timestamp": time.time(),
            }
            return jsonify({"id": audit_id, "status": "error", "message": str(e)}), 200

        result = scanner.scan(repo_url, files)
        _audits[audit_id] = {
            "id": audit_id, "status": "completed", "repo_url": repo_url,
            "permission_granted": True, "timestamp": time.time(), "result": result,
        }
        return jsonify({
            "id": audit_id, "status": "completed",
            "score": result.get("score"),
            "findings_count": result.get("findings_count", 0),
            "findings": result.get("findings"),
            "skipped_files": result.get("skipped_files", []),
        }), 200

    except Exception as e:
        _audits[audit_id] = {
            "id": audit_id, "status": "error",
            "repo_url": repo_url, "error": str(e), "timestamp": time.time(),
        }
        return jsonify({"id": audit_id, "status": "error", "message": str(e)}), 500


@auditor_bp.route('/api/v1/audit/stream', methods=['GET'])
def audit_stream():
    """Auditoría progresiva via Server-Sent Events.

    Emite eventos en 3 fases:
    1. enumeration: lista de archivos encontrados
    2. file_scanned: resultado por archivo (clean/findings/critical)
    3. complete: score final y hallazgos

    Query Params:
        repo_url: URL del repositorio GitHub
    """
    repo_url = request.args.get('repo_url', '').strip()
    if not repo_url:
        return jsonify({"error": "bad_request", "message": "repo_url requerido"}), 400

    def event_stream():
        from src.auditor.github_fetcher import GitHubFetcher, GitHubFetchError
        from src.auditor.scanner import AuditScanner, MAX_FILE_SIZE_KB, SUPPORTED_EXTENSIONS

        # FASE 1: Descargar y enumerar archivos
        yield _sse({"type": "phase", "phase": "enumeration", "message": "Descargando árbol de archivos..."})

        fetcher = GitHubFetcher()
        try:
            files = fetcher.fetch_repo_files(repo_url)
        except GitHubFetchError as e:
            yield _sse({"type": "error", "message": str(e)})
            return

        # Clasificar archivos
        analyzable = [f for f in files if not f.get('skipped')]
        skipped = [f for f in files if f.get('skipped')]

        yield _sse({
            "type": "enumeration",
            "total": len(files),
            "analyzable": len(analyzable),
            "skipped": len(skipped),
            "files": [f["path"] for f in analyzable],
            "skipped_files": [{"path": f["path"], "reason": f.get("reason", "")} for f in skipped[:10]],
        })

        # FASE 2: Escanear archivo por archivo
        yield _sse({"type": "phase", "phase": "scanning", "message": "Escaneando archivos..."})

        secrets_detector = SecretsDetector()
        iac_inspector = IaCInspector()
        governance_checker = GovernanceChecker()
        all_secrets = []
        all_iac = []
        scanned_count = 0

        for file_info in analyzable:
            path = file_info.get("path", "")
            content = file_info.get("content", "")
            scanned_count += 1

            # Escanear este archivo
            file_secrets = secrets_detector.scan([file_info])
            file_iac = iac_inspector.scan([file_info])

            all_secrets.extend(file_secrets)
            all_iac.extend(file_iac)

            finding_count = len(file_secrets) + len(file_iac)

            if finding_count == 0:
                status = "clean"
            elif any(f.get("severity") == "critical" for f in file_secrets):
                status = "critical"
            else:
                status = "findings"

            yield _sse({
                "type": "file_scanned",
                "path": path,
                "status": status,
                "findings_count": finding_count,
                "current": scanned_count,
                "total": len(analyzable),
            })

            # Pequeña pausa para que la animación sea visible
            time.sleep(0.1)

        # Governance check (contra todos los archivos)
        all_governance = governance_checker.check(files)

        # FASE 3: Calcular score y emitir resultado final
        yield _sse({"type": "phase", "phase": "calculating", "message": "Calculando score de seguridad..."})

        calculator = ScoreCalculator()
        score = calculator.calculate(all_secrets, all_iac, all_governance)

        total_findings = len(all_secrets) + len(all_iac) + len(all_governance)
        clean_files = len(analyzable) - len({f["file"] for f in all_secrets + all_iac})

        yield _sse({
            "type": "complete",
            "score": score,
            "findings_count": total_findings,
            "findings": {
                "secrets": all_secrets,
                "iac": all_iac,
                "governance": all_governance,
            },
            "summary": {
                "total_files": len(files),
                "analyzed": len(analyzable),
                "clean": clean_files,
                "with_findings": len(analyzable) - clean_files,
                "skipped": len(skipped),
            },
            "skipped_files": [{"path": f["path"], "reason": f.get("reason", "")} for f in skipped],
        })

    return Response(
        stream_with_context(event_stream()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )


def _sse(data: dict) -> str:
    """Formatea un evento SSE."""
    return f"data: {json.dumps(data, default=str)}\n\n"


@auditor_bp.route('/api/v1/audit/<audit_id>/status', methods=['GET'])
def audit_status(audit_id: str):
    """Retorna el estado de una auditoría."""
    audit = _audits.get(audit_id)
    if not audit:
        return jsonify({"error": "not_found", "message": "Auditoría no encontrada"}), 404
    return jsonify({"id": audit_id, "status": audit["status"], "repo_url": audit.get("repo_url")})


@auditor_bp.route('/api/v1/audit/<audit_id>/report', methods=['GET'])
def audit_report(audit_id: str):
    """Retorna el reporte completo de una auditoría."""
    audit = _audits.get(audit_id)
    if not audit:
        return jsonify({"error": "not_found", "message": "Auditoría no encontrada"}), 404
    if audit["status"] == "cancelled":
        return jsonify({"id": audit_id, "status": "cancelled", "message": "Auditoría cancelada — No se accedió a ningún dato"})
    return jsonify({"id": audit_id, "status": audit["status"], "result": audit.get("result", {})})
