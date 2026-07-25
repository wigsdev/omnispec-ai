"""Auditor Routes — Endpoints de Auditoría 3D (US-2).

Endpoints:
    POST /api/v1/audit          — Inicia auditoría 3D
    GET  /api/v1/audit/<id>/status — Estado de auditoría
    GET  /api/v1/audit/<id>/report — Reporte completo
"""

import time
import uuid

from flask import Blueprint, jsonify, request

from src.auditor.scanner import AuditScanner

auditor_bp = Blueprint('auditor', __name__)

# Almacén en memoria de auditorías (dev/test)
_audits: dict = {}


@auditor_bp.route('/api/v1/audit', methods=['POST'])
def start_audit():
    """Inicia una auditoría 3D de un repositorio GitHub.

    Protocolo Human-in-the-Loop: Si permission_granted != true,
    retorna 200 con status "cancelled" sin llamar a GitHub API.

    Request Body:
        {
            "repo_url": "https://github.com/user/repo",
            "permission_granted": true/false
        }
    """
    data = request.get_json(silent=True)
    if not data or not data.get('repo_url'):
        return jsonify({
            "error": "bad_request",
            "message": "El campo 'repo_url' es requerido"
        }), 400

    repo_url = data['repo_url'].strip()
    permission_granted = data.get('permission_granted', False)

    # GAP-2: Guard clause — permission check antes de cualquier operación
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

    # Permission granted — proceder con auditoría
    audit_id = str(uuid.uuid4())
    scanner = AuditScanner()

    try:
        result = scanner.scan(repo_url)
        _audits[audit_id] = {
            "id": audit_id,
            "status": "completed",
            "repo_url": repo_url,
            "permission_granted": True,
            "timestamp": time.time(),
            "result": result,
        }
        return jsonify({
            "id": audit_id,
            "status": "completed",
            "score": result.get("score"),
            "findings_count": result.get("findings_count", 0),
        }), 200

    except Exception as e:
        _audits[audit_id] = {
            "id": audit_id,
            "status": "error",
            "repo_url": repo_url,
            "error": str(e),
            "timestamp": time.time(),
        }
        return jsonify({
            "id": audit_id,
            "status": "error",
            "message": str(e),
        }), 500


@auditor_bp.route('/api/v1/audit/<audit_id>/status', methods=['GET'])
def audit_status(audit_id: str):
    """Retorna el estado de una auditoría."""
    audit = _audits.get(audit_id)
    if not audit:
        return jsonify({"error": "not_found", "message": "Auditoría no encontrada"}), 404

    return jsonify({
        "id": audit_id,
        "status": audit["status"],
        "repo_url": audit.get("repo_url"),
    })


@auditor_bp.route('/api/v1/audit/<audit_id>/report', methods=['GET'])
def audit_report(audit_id: str):
    """Retorna el reporte completo de una auditoría."""
    audit = _audits.get(audit_id)
    if not audit:
        return jsonify({"error": "not_found", "message": "Auditoría no encontrada"}), 404

    if audit["status"] == "cancelled":
        return jsonify({
            "id": audit_id,
            "status": "cancelled",
            "message": "Auditoría cancelada — No se accedió a ningún dato",
        })

    return jsonify({
        "id": audit_id,
        "status": audit["status"],
        "result": audit.get("result", {}),
    })
