"""PatchValidator — Ejecutor de pytest en entorno aislado.

Ejecuta tests generados con subprocess.run(timeout=30) para
validar patches antes de crear PRs. Bloquea el PR si falla.
"""

import os
import subprocess
import sys
import tempfile
from typing import Any


class PatchValidator:
    """Validador de patches mediante ejecución de pytest.

    Ejecuta los tests generados en un directorio temporal
    aislado usando subprocess para no contaminar el proceso.
    """

    def validate(self, test_content: str, timeout: int = 30) -> dict[str, Any]:
        """Ejecuta pytest sobre el contenido de test proporcionado.

        Args:
            test_content: Código Python de los tests a ejecutar.
            timeout: Timeout en segundos para la ejecución.

        Returns:
            Dict con:
                - passed: True si todos los tests pasan
                - output: Stdout/stderr completo de pytest
                - return_code: Exit code del proceso
        """
        if not test_content or not test_content.strip():
            return {
                "passed": False,
                "output": "Error: test content is empty",
                "return_code": -1,
            }

        # Crear archivo temporal con los tests
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.py', prefix='test_security_patch_',
            delete=False, encoding='utf-8'
        ) as f:
            f.write(test_content)
            test_file = f.name

        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pytest', test_file, '--tb=short', '-q'],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tempfile.gettempdir(),
            )

            return {
                "passed": result.returncode == 0,
                "output": result.stdout + result.stderr,
                "return_code": result.returncode,
            }

        except subprocess.TimeoutExpired:
            return {
                "passed": False,
                "output": f"Error: pytest timed out after {timeout}s",
                "return_code": -2,
            }
        except FileNotFoundError:
            return {
                "passed": False,
                "output": "Error: pytest not found in PATH",
                "return_code": -3,
            }
        finally:
            # Cleanup
            try:
                os.unlink(test_file)
            except OSError:
                pass
