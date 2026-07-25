"""Fixer Routes — Endpoints del Auto-Fix Engine (US-3).

Endpoints:
    POST /api/v1/fix/generate  — Genera diff + tests
    POST /api/v1/fix/apply     — Crea branch + PR (con permiso)
    GET  /api/v1/fix/<id>/status — Estado del fix/PR
"""

import time
import uuid

from flask import Blueprint, jsonify, request

from src.pr_engine.fixer import DiffFixer
from src.pr_engine.test_generator import TestSuiteGenerator
from src.pr_engine.validator import PatchValidator
from src.pr_engine.pr_creator import PRCreator

fixer_bp = Blueprint('fixer', __name__)

# Almacén en memoria de fixes (dev/test)
_fixes: dict = {}


@fixer_bp.route('/api/v1/fix/generate', methods=['POST'])
def generate_fix():
    """Genera parche diff y tests para hallazgos seleccionados.

    Request Body:
        {"findings": [...], "repo_url": "..."}
    """
    data = request.get_json(silent=True)
    if not data or not data.get('findings'):
        return jsonify({
            "error": "bad_request",
            "message": "El campo 'findings' es requerido"
        }), 400

    findings = data['findings']
    repo_url = data.get('repo_url', '')

    fixer = DiffFixer()
    test_gen = TestSuiteGenerator()

    try:
        # Fetch archivos originales si tenemos repo URL (para fix directo)
        repo_files = None
        if repo_url:
            try:
                from src.auditor.github_fetcher import GitHubFetcher
                fetcher = GitHubFetcher()
                repo_files = [f for f in fetcher.fetch_repo_files(repo_url) if not f.get('skipped')]
            except Exception:
                repo_files = None

        diff_result = fixer.generate(findings, files=repo_files)

        # No fix needed
        if diff_result.get("status") in ("no_fix_needed", "error"):
            return jsonify(diff_result), 200

        test_result = test_gen.generate(findings, diff_result.get("diff", ""))

        fix_id = str(uuid.uuid4())
        _fixes[fix_id] = {
            "id": fix_id,
            "status": "generated",
            "diff": diff_result.get("diff", ""),
            "fixed_files": diff_result.get("fixed_files", {}),
            "tests": test_result["test_content"],
            "repo_url": repo_url,
            "findings": findings,
            "provider": diff_result.get("provider", "unknown"),
            "latency_ms": diff_result.get("latency_ms", 0),
            "timestamp": time.time(),
        }

        return jsonify({
            "id": fix_id,
            "status": "generated",
            "diff": diff_result.get("diff", ""),
            "tests": test_result["test_content"],
            "files_changed": diff_result.get("files_changed", 0),
            "provider": diff_result.get("provider"),
            "latency_ms": diff_result.get("latency_ms"),
        }), 200

    except Exception as e:
        return jsonify({
            "error": "generation_failed",
            "message": str(e)
        }), 500


@fixer_bp.route('/api/v1/fix/apply', methods=['POST'])
def apply_fix():
    """Aplica el fix creando branch y PR en GitHub.

    Protocolo HitL: Si write_permission_granted != true,
    retorna 200 con download habilitado sin crear PR.

    Request Body:
        {"fix_id": "...", "write_permission_granted": true/false}
    """
    data = request.get_json(silent=True)
    if not data or not data.get('fix_id'):
        return jsonify({
            "error": "bad_request",
            "message": "El campo 'fix_id' es requerido"
        }), 400

    fix_id = data['fix_id']
    write_permission = data.get('write_permission_granted', False)

    fix_data = _fixes.get(fix_id)
    if not fix_data:
        return jsonify({"error": "not_found", "message": "Fix no encontrado"}), 404

    # GAP-2: Guard clause — write permission check in router
    if not write_permission:
        _fixes[fix_id]["status"] = "cancelled"
        _fixes[fix_id]["permission_granted"] = False
        return jsonify({
            "id": fix_id,
            "status": "cancelled",
            "message": "PR cancelado — Archivos disponibles para descarga local",
            "download_available": True,
            "diff_content": fix_data["diff"],
            "test_content": fix_data["tests"],
            "write_permission_granted": False,
        }), 200

    # Permission granted — validate and create PR
    validator = PatchValidator()
    validation = validator.validate(fix_data["tests"])

    if not validation["passed"]:
        _fixes[fix_id]["status"] = "validation_failed"
        return jsonify({
            "id": fix_id,
            "status": "validation_failed",
            "message": "Tests fallaron — PR no creado",
            "pytest_output": validation["output"],
        }), 200

    # Create PR
    from src.api.routes.auth import get_user_github_token
    user_token = get_user_github_token()
    if not user_token:
        return jsonify({
            "id": fix_id,
            "status": "auth_required",
            "message": "Debes conectar tu cuenta de GitHub primero",
        }), 200

    pr_creator = PRCreator(github_token=user_token)
    try:
        pr_result = pr_creator.create_pr(
            repo_url=fix_data["repo_url"],
            diff=fix_data["diff"],
            tests=fix_data["tests"],
            findings=fix_data["findings"],
            fixed_files=fix_data.get("fixed_files"),
        )
        _fixes[fix_id]["status"] = "pr_created"
        _fixes[fix_id]["pr_url"] = pr_result.get("pr_url")

        return jsonify({
            "id": fix_id,
            "status": "pr_created",
            "pr_url": pr_result.get("pr_url"),
            "branch": pr_result.get("branch"),
        }), 200

    except Exception as e:
        _fixes[fix_id]["status"] = "error"
        return jsonify({
            "id": fix_id,
            "status": "error",
            "message": str(e),
        }), 500


@fixer_bp.route('/api/v1/fix/<fix_id>/status', methods=['GET'])
def fix_status(fix_id: str):
    """Retorna el estado de un fix."""
    fix_data = _fixes.get(fix_id)
    if not fix_data:
        return jsonify({"error": "not_found", "message": "Fix no encontrado"}), 404

    return jsonify({
        "id": fix_id,
        "status": fix_data["status"],
        "pr_url": fix_data.get("pr_url"),
    })
