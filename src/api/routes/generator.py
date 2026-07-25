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
        provider = result.get("provider", "unknown")
        model = result.get("metadata", {}).get("model", "unknown")
        latency = result.get("latency_ms", 0)

        # Generar los 4 documentos completos con IA
        requirements_content = result["content"]
        design_content = _generate_design(gen, prompt, provider)
        tasks_content = _generate_tasks(gen, prompt, provider)
        agents_content = _generate_agents_professional(prompt, provider)

        # Firma en requirements (los otros ya la tienen de sus helpers)
        req_signature = _build_signature(provider, model, latency)
        requirements_signed = requirements_content + req_signature

        # Firma ya está incluida por las funciones _generate_*

        return jsonify({
            "data": requirements_content,
            "documents": {
                "requirements": requirements_signed,
                "design": design_content,
                "tasks": tasks_content,
                "agents": agents_content,
            },
            "metadata": result.get("metadata", {}),
            "provider": provider,
            "model": model,
            "latency_ms": latency,
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

    Genera los 4 documentos completos usando AIRouter:
    - requirements.md (SDD EARS completo)
    - design.md (arquitectura y decisiones)
    - tasks.md (plan de implementación)
    - AGENTS.md (gobernanza profesional)

    Request Body:
        {"prompt": "Descripción del proyecto"}

    Returns:
        ZIP file con los 4 documentos generados por IA.
    """
    data = request.get_json(silent=True)
    if not data or not data.get('prompt'):
        return jsonify({"error": "bad_request", "message": "El campo 'prompt' es requerido"}), 400

    prompt = data['prompt'].strip()
    gen = _get_generator()

    try:
        # Generar requirements.md (SDD principal)
        result = gen.generate(prompt)
        requirements_content = _sanitize_mermaid(result["content"])
        provider = result.get("provider", "SmartEngine")
        model = result.get("metadata", {}).get("model", "unknown")
        latency = result.get("latency_ms", 0)

        # Generar design.md con IA
        design_content = _generate_design(gen, prompt, provider)

        # Generar tasks.md con IA
        tasks_content = _generate_tasks(gen, prompt, provider)

        # Generar AGENTS.md profesional
        agents_content = _generate_agents_professional(prompt, provider)

        # Crear ZIP en memoria
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('.kiro/specs/app/requirements.md', requirements_content)
            zf.writestr('.kiro/specs/app/design.md', design_content)
            zf.writestr('.kiro/specs/app/tasks.md', tasks_content)
            zf.writestr('AGENTS.md', agents_content)

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


def _sanitize_mermaid(content: str) -> str:
    """Sanitiza sintaxis Mermaid inválida generada por LLMs.

    Corrige patrones comunes como |> que Mermaid no parsea.
    """
    import re
    # Fix: -->|label|> Node → -->|label| Node
    content = re.sub(r'\|>\s*', '| ', content)
    # Fix: stray > after pipe-labels at end of line
    content = re.sub(r'\|>(\s*\n)', r'|\1', content)
    return content


def _generate_design(gen, prompt: str, provider: str) -> str:
    """Genera design.md completo con IA."""
    design_prompt = (
        f"Genera un documento de diseño técnico (design.md) para el siguiente proyecto:\n\n"
        f"{prompt}\n\n"
        f"Incluye las siguientes secciones:\n"
        f"1. Arquitectura General (con diagrama Mermaid graph TB)\n"
        f"2. Stack Tecnológico (tabla)\n"
        f"3. Componentes Principales (descripción de cada módulo)\n"
        f"4. Flujo de Datos (diagrama de secuencia Mermaid)\n"
        f"5. Decisiones de Diseño (tabla con justificaciones)\n\n"
        f"Output: Markdown puro sin code fences envolventes. Empieza directamente con # Design Document"
    )

    result = gen.router.generate(prompt=design_prompt, system_prompt="")
    content = _sanitize_mermaid(result["content"])
    signature = _build_signature(result.get("provider", provider), result.get("model", "unknown"), result.get("latency_ms", 0))
    return content + signature


def _generate_tasks(gen, prompt: str, provider: str) -> str:
    """Genera tasks.md completo con IA."""
    tasks_prompt = (
        f"Genera un plan de tareas de implementación (tasks.md) para el siguiente proyecto:\n\n"
        f"{prompt}\n\n"
        f"Incluye:\n"
        f"1. Tareas secuenciales con checkbox [ ] y referencia a REQ-x.x\n"
        f"2. Al menos 8 tareas específicas y accionables\n"
        f"3. Dependencias entre tareas\n"
        f"4. Criterios de completitud (DoD) por tarea\n\n"
        f"Output: Markdown puro sin code fences envolventes. Empieza directamente con # Plan de Tareas"
    )

    result = gen.router.generate(prompt=tasks_prompt, system_prompt="")
    content = result["content"]
    signature = _build_signature(result.get("provider", provider), result.get("model", "unknown"), result.get("latency_ms", 0))
    return content + signature


def _build_signature(provider: str, model: str, latency_ms: float) -> str:
    """Construye la firma de generación al final del documento."""
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"\n\n---\n\n"
        f"> **Generado por OmniSpec AI**\n"
        f"> Proveedor: {provider} ({model})\n"
        f"> Latencia: {latency_ms:.0f} ms\n"
        f"> Fecha: {ts}\n"
        f"> Plataforma: OmniSpec AI — Multi-Provider AIRouter\n"
    )


def _generate_agents_professional(prompt: str, provider: str) -> str:
    """Genera un AGENTS.md profesional y contextualizado."""
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Extraer nombre corto del proyecto
    words = prompt.strip().split()
    project_name = " ".join(words[:8]) if len(words) > 8 else prompt

    return f"""# AGENTS.md — Gobernanza Agéntica

> Documento generado por OmniSpec AI | {ts}
> Proveedor: {provider}

---

## Proyecto

**{project_name}**

{prompt}

---

## Definition of Done (DoD)

Una tarea se considera **completada** cuando cumple TODOS los siguientes criterios:

1. El código compila y ejecuta sin errores en el entorno objetivo.
2. Todos los tests unitarios pasan exitosamente (`pytest --tb=short -q`).
3. La cobertura de tests no disminuye respecto a la rama principal (mínimo 80%).
4. El código sigue las convenciones del proyecto (PEP 8, type hints, docstrings Google Style).
5. No se introducen dependencias nuevas sin justificación documentada en el PR.
6. Los cambios están commiteados en una rama feature con mensaje descriptivo (Conventional Commits).
7. La documentación se actualiza junto al código cuando aplica.
8. El PR incluye descripción del cambio, evidencia de tests, y referencia al requisito EARS (REQ-x.x).

---

## Reglas TDD (pytest)

- **Red-Green-Refactor**: Test que falla primero → mínimo código para que pase → refactorizar.
- **Framework**: pytest con fixtures, parametrize, y markers.
- **Estructura**: Espejo de `src/` dentro de `tests/` (e.g., `src/module/x.py` → `tests/module/test_x.py`).
- **Naming**: `test_<función>_<escenario>_<resultado_esperado>`.
- **Mocks**: `unittest.mock` o `pytest-mock` para dependencias externas (APIs, DB, red).
- **Cobertura mínima**: 80% por módulo (`pytest --cov=src --cov-report=term-missing`).
- **Ejecución pre-commit**: `pytest --tb=short -q` antes de cada commit.

---

## Sintaxis EARS para Especificaciones

Todos los requisitos funcionales DEBEN usar sintaxis **EARS** (Easy Approach to Requirements Syntax):

| Patrón | Plantilla |
|--------|-----------|
| Ubiquitous | The system shall `<response>`. |
| Event-Driven | When `<trigger>`, the system shall `<response>`. |
| State-Driven | While `<state>`, the system shall `<response>`. |
| Unwanted Behavior | If `<condition>`, then the system shall `<response>`. |
| Optional Feature | Where `<feature>` is supported, the system shall `<response>`. |

---

## Estándar de Commits (Conventional Commits)

```
<tipo>(<módulo>): <descripción en presente imperativo>
```

| Tipo | Uso |
|------|-----|
| `feat` | Nueva funcionalidad |
| `fix` | Corrección de bug |
| `test` | Tests unitarios |
| `docs` | Documentación |
| `refactor` | Mejora sin cambio funcional |
| `infra` | Infraestructura / IaC |

---

## Reglas de Desarrollo Agéntico

1. **Autonomía acotada**: Ejecutar solo tareas definidas en el backlog sin desviarse del scope.
2. **Verificación continua**: Después de cada cambio, ejecutar build + tests para validar.
3. **Fail-fast**: Si un approach falla 2 veces, diagnosticar root cause y proponer alternativa.
4. **No gold-plating**: Implementar exactamente lo pedido, sin features adicionales.
5. **Trazabilidad**: Cada cambio vinculado a un requisito EARS (REQ-x.x).
6. **Seguridad por defecto**: Validar inputs, queries parametrizadas, manejo explícito de errores.
7. **Commits atómicos**: Un commit por unidad lógica de cambio.
8. **Documentación inline**: Type hints + docstrings Google Style en funciones públicas.

---

## Calidad de Código Python

- **Type Hints**: Obligatorios en todas las funciones públicas.
- **Docstrings**: Formato Google Style (Args, Returns, Raises).
- **Linting**: `ruff check src/ tests/`
- **Formatting**: `ruff format src/ tests/`
- **Type Checking**: `mypy src/ --strict`

---

> Generado por OmniSpec AI — Multi-Provider AIRouter
> Proveedor: {provider} | Fecha: {ts}
"""
