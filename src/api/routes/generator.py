"""Generator Routes — Endpoints del SDD Generator (US-1).

Endpoints:
    POST /api/v1/generate       — Genera SDD spec completa
    GET  /api/v1/generate/stream — SSE streaming de generación
    POST /api/v1/generate/export — Exporta Pack .kiro (ZIP)
"""

import io
import json
import time
import zipfile

from flask import Blueprint, Response, jsonify, request, stream_with_context

from src.sdd_generator.generator import SDDGenerator

generator_bp = Blueprint('generator', __name__)

# Instancia del generador (lazy init)
_generator: SDDGenerator | None = None


def _get_generator() -> SDDGenerator:
    """Obtiene o crea la instancia del generador."""
    global _generator
    if _generator is None:
        _generator = SDDGenerator()
    return _generator


@generator_bp.route('/api/v1/generate', methods=['POST'])
def generate():
    """Genera una especificación SDD completa.

    Request Body:
        {"prompt": "Descripción del proyecto"}

    Returns:
        JSON con la especificación generada.
    """
    data = request.get_json(silent=True)
    if not data or not data.get('prompt'):
        return jsonify({"error": "bad_request", "message": "El campo 'prompt' es requerido"}), 400

    prompt = data['prompt'].strip()
    gen = _get_generator()

    try:
        result = gen.generate(prompt)
        return jsonify({
            "data": result["content"],
            "metadata": result.get("metadata", {}),
            "provider": result.get("provider"),
            "latency_ms": result.get("latency_ms"),
            "fallback": result.get("fallback", None)
        })
    except Exception as e:
        return jsonify({"error": "generation_failed", "message": str(e)}), 500


@generator_bp.route('/api/v1/generate/stream', methods=['GET'])
def generate_stream():
    """Genera SDD via Server-Sent Events (streaming).

    Query Params:
        prompt: Descripción del proyecto

    Returns:
        SSE stream con chunks incrementales.
    """
    prompt = request.args.get('prompt', '').strip()
    if not prompt:
        return jsonify({"error": "bad_request", "message": "El parámetro 'prompt' es requerido"}), 400

    gen = _get_generator()

    def event_stream():
        start = time.time()
        seq = 0

        try:
            for chunk in gen.stream_generate(prompt):
                elapsed = time.time() - start
                seq += 1
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk, 'seq': seq, 'elapsed': round(elapsed, 2)})}\n\n"

                if elapsed > 25:
                    yield f"data: {json.dumps({'type': 'timeout_warning', 'elapsed': round(elapsed, 2)})}\n\n"

            yield f"data: {json.dumps({'type': 'complete', 'total_chunks': seq, 'elapsed': round(time.time() - start, 2)})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return Response(
        stream_with_context(event_stream()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )


@generator_bp.route('/api/v1/generate/export', methods=['POST'])
def generate_export():
    """Exporta un Pack .kiro como archivo ZIP.

    Request Body:
        {"prompt": "Descripción del proyecto"}

    Returns:
        ZIP file con requirements.md, design.md, tasks.md, AGENTS.md.
    """
    data = request.get_json(silent=True)
    if not data or not data.get('prompt'):
        return jsonify({"error": "bad_request", "message": "El campo 'prompt' es requerido"}), 400

    prompt = data['prompt'].strip()
    gen = _get_generator()

    try:
        result = gen.generate(prompt)
        content = result["content"]

        # Crear ZIP en memoria
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('.kiro/specs/app/requirements.md', content)
            zf.writestr('.kiro/specs/app/design.md', _generate_design_stub(prompt))
            zf.writestr('.kiro/specs/app/tasks.md', _generate_tasks_stub(prompt))
            zf.writestr('AGENTS.md', _generate_agents_stub())

        zip_buffer.seek(0)

        return Response(
            zip_buffer.getvalue(),
            mimetype='application/zip',
            headers={
                'Content-Disposition': 'attachment; filename=omnispec-pack.kiro.zip'
            }
        )
    except Exception as e:
        return jsonify({"error": "export_failed", "message": str(e)}), 500


def _generate_design_stub(prompt: str) -> str:
    """Genera un stub de design.md para el pack."""
    return f"# Design Document\n\n## Proyecto\n\n{prompt}\n\n## Arquitectura\n\nPendiente de generación detallada.\n"


def _generate_tasks_stub(prompt: str) -> str:
    """Genera un stub de tasks.md para el pack."""
    return f"# Plan de Tareas\n\n## Proyecto\n\n{prompt}\n\n- [ ] Tarea 1: Definir arquitectura\n- [ ] Tarea 2: Implementar core\n- [ ] Tarea 3: Tests\n"


def _generate_agents_stub() -> str:
    """Genera un AGENTS.md básico para el pack."""
    return """# AGENTS.md

## Definition of Done (DoD)

1. El código compila/ejecuta sin errores.
2. Todos los tests unitarios pasan.
3. El código sigue las convenciones del proyecto.

## Reglas TDD

- Framework: pytest
- Cobertura mínima: 80%
- Naming: test_<función>_<escenario>_<resultado>
"""
