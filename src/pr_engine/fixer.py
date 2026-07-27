"""DiffFixer — Generador de correcciones de seguridad con AIRouter.

Genera archivos corregidos (contenido completo) para cada vulnerabilidad
detectada. También produce el diff para preview en la UI.

Solo procesa hallazgos con severidad accionable (critical, high, medium).
Hallazgos con severidad 'info' (archivos de test) y 'low' (valores de
ejemplo en producción) se excluyen del pipeline de fix automático.
"""

from typing import Any

# Severidades que ameritan un fix automático.
# - 'info'  → archivos de test: falsos positivos intencionales, nunca tocar.
# - 'low'   → valores de ejemplo en producción: merecen revisión humana
#             pero no un PR automático que podría romper código de docs/demos.
ACTIONABLE_SEVERITIES: frozenset[str] = frozenset({"critical", "high", "medium"})

from src.sdd_generator.ai_router import UniversalAIRouter

ROLE_3_FIX_PROMPT = """You are a Security Remediation Engineer. Fix the security vulnerability in the file below.

Rules:
- Return ONLY the complete fixed file content, no explanations, no markdown fences.
- Fix ONLY the identified vulnerability (minimal change principle).
- Replace hardcoded secrets with environment variable references (os.environ.get or os.getenv).
- Replace exposed keys with placeholder comments.
- Keep all other code unchanged.
- Maintain the same file structure and formatting.

Vulnerability: {description}
File: {file_path}
Line: {line}

Original file content:
{file_content}
"""

ROLE_3_DIFF_PROMPT = """You are a Test Automation Engineer. Generate a unified diff showing the security fixes.

Rules:
- Output ONLY the unified diff, no explanation, no markdown fences.
- Start each file with --- a/ and +++ b/ lines.
- Fix ONLY the identified vulnerabilities.
- Show context lines around changes.

Vulnerabilities to fix:
{findings_text}
"""


class DiffFixer:
    """Generador de correcciones de seguridad.

    Genera tanto archivos corregidos (para el PR) como
    diffs de preview (para la UI).
    """

    def __init__(self, ai_router: UniversalAIRouter | None = None, gemini_client=None):
        """Inicializa el fixer."""
        if gemini_client is not None:
            from src.sdd_generator.ai_router import AIProvider, ProviderError, SmartEngineProvider
            from src.sdd_generator.gemini_client import (
                GeminiClient, MissingAPIKeyError, RateLimitError, GeminiClientError,
            )

            class LegacyProvider(AIProvider):
                name = "Gemini"
                model = "legacy"
                def __init__(self, client):
                    self._client = client
                def is_available(self):
                    return self._client.is_available
                def generate(self, prompt, system_prompt=""):
                    try:
                        result = self._client.generate(prompt=prompt, system_prompt=system_prompt)
                        return result["content"]
                    except (MissingAPIKeyError, RateLimitError, GeminiClientError) as e:
                        raise ProviderError("Gemini", str(e))

            self.router = UniversalAIRouter(providers=[LegacyProvider(gemini_client), SmartEngineProvider()])
        else:
            self.router = ai_router or UniversalAIRouter()

    def generate(self, findings: list[dict[str, Any]], files: list[dict] | None = None) -> dict[str, Any]:
        """Genera correcciones para los hallazgos detectados.

        Solo procesa findings con severidad accionable (critical, high, medium).
        Findings con severidad 'info' (archivos de test) o 'low' (valores de
        ejemplo conocidos) se excluyen del pipeline de fix automático.

        Args:
            findings: Lista de hallazgos de seguridad.
            files: Archivos originales del repo (con 'path' y 'content').

        Returns:
            Dict con 'diff' (preview), 'fixed_files' (contenido corregido),
            'status', 'provider', 'latency_ms'.
        """
        if not findings:
            return {"status": "no_fix_needed", "message": "No hay hallazgos para corregir"}

        # Filtrar: solo hallazgos que ameritan intervención automática
        actionable = [
            f for f in findings
            if f.get("severity", "").lower() in ACTIONABLE_SEVERITIES
        ]
        skipped_count = len(findings) - len(actionable)

        if not actionable:
            return {
                "status": "no_fix_needed",
                "message": (
                    f"No hay hallazgos accionables. "
                    f"{skipped_count} hallazgo(s) con severidad 'info'/'low' "
                    f"fueron excluidos (archivos de test o valores de ejemplo)."
                ),
                "skipped": skipped_count,
            }

        # Si se descartaron algunos, registrarlo en el resultado
        excluded_info = {"skipped_low_info": skipped_count} if skipped_count > 0 else {}

        # Si tenemos los archivos originales, generar fixes por archivo
        if files:
            result = self._generate_file_fixes(actionable, files)
        else:
            # Sin archivos originales, generar solo el diff (legacy)
            result = self._generate_diff_only(actionable)

        return {**result, **excluded_info}

    def _generate_file_fixes(
        self, findings: list[dict[str, Any]], files: list[dict]
    ) -> dict[str, Any]:
        """Genera contenido corregido por archivo."""
        fixed_files: dict[str, str] = {}
        total_latency = 0

        # Agrupar findings por archivo
        findings_by_file: dict[str, list] = {}
        for f in findings:
            path = f.get("file", "")
            if path not in findings_by_file:
                findings_by_file[path] = []
            findings_by_file[path].append(f)

        # Buscar contenido original de cada archivo afectado
        file_contents: dict[str, str] = {f["path"]: f.get("content", "") for f in files}

        provider_used = "unknown"

        for file_path, file_findings in findings_by_file.items():
            original_content = file_contents.get(file_path, "")
            if not original_content:
                continue

            # Generar fix para este archivo
            description = "; ".join(f.get("description", "") for f in file_findings)
            prompt = ROLE_3_FIX_PROMPT.format(
                description=description,
                file_path=file_path,
                line=file_findings[0].get("line", "?"),
                file_content=original_content,
            )

            result = self.router.generate(prompt=prompt, system_prompt="")
            fixed_content = self._clean_output(result["content"])
            provider_used = result.get("provider", provider_used)
            total_latency += result.get("latency_ms", 0)

            # Solo incluir si realmente cambió algo
            if fixed_content and fixed_content.strip() != original_content.strip():
                fixed_files[file_path] = fixed_content

        if not fixed_files:
            return {"status": "no_fix_needed", "message": "No se generaron cambios"}

        # Generar diff para preview (comparando original vs fixed)
        diff_preview = self._build_diff_preview(fixed_files, file_contents)

        return {
            "status": "generated",
            "diff": diff_preview,
            "fixed_files": fixed_files,
            "files_changed": len(fixed_files),
            "provider": provider_used,
            "latency_ms": total_latency,
        }

    def _generate_diff_only(self, findings: list[dict[str, Any]]) -> dict[str, Any]:
        """Genera solo el diff (sin archivos originales)."""
        findings_text = "\n".join(
            f"- [{f.get('severity')}] {f.get('description')} in {f.get('file')}:{f.get('line')}"
            for f in findings
        )
        prompt = ROLE_3_DIFF_PROMPT.format(findings_text=findings_text)

        result = self.router.generate(prompt=prompt, system_prompt="")
        content = self._clean_output(result["content"])
        provider = result.get("provider", "unknown")
        latency = result.get("latency_ms", 0)

        if provider == "SmartEngine" or not self._is_valid_diff(content):
            return {
                "status": "error",
                "message": "No se pudo generar un diff válido",
                "diff": "",
                "provider": provider,
                "latency_ms": latency,
            }

        return {
            "status": "generated",
            "diff": content,
            "fixed_files": {},
            "provider": provider,
            "latency_ms": latency,
        }

    def _build_diff_preview(
        self, fixed_files: dict[str, str], originals: dict[str, str]
    ) -> str:
        """Construye un diff legible para preview en la UI."""
        import difflib
        diff_lines = []

        for path, fixed in fixed_files.items():
            original = originals.get(path, "")
            orig_lines = original.splitlines(keepends=True)
            fixed_lines = fixed.splitlines(keepends=True)

            file_diff = difflib.unified_diff(
                orig_lines, fixed_lines,
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
                lineterm=""
            )
            diff_lines.extend(file_diff)

        return "\n".join(diff_lines) if diff_lines else ""

    def _clean_output(self, content: str) -> str:
        """Limpia code fences del output de la IA."""
        clean = content.strip()
        if clean.startswith("```python"):
            clean = clean[len("```python"):].strip()
        elif clean.startswith("```"):
            clean = clean[3:].strip()
        if clean.endswith("```"):
            clean = clean[:-3].strip()
        return clean

    def _is_valid_diff(self, diff_text: str) -> bool:
        """Valida formato de diff."""
        if not diff_text:
            return False
        return ('---' in diff_text or '@@' in diff_text) and ('+' in diff_text or '-' in diff_text)
