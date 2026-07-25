"""ScoreCalculator — Cálculo de Score de Seguridad Ponderado.

Fórmula: Score = 100 - (secrets_penalty * 0.5 + iac_penalty * 0.3 + gov_penalty * 0.2)
Resultado acotado: max(0, min(100, score))

Severidades:
    - Crítico: penalty 20
    - Alto: penalty 10
    - Medio: penalty 5
    - Bajo: penalty 2
"""

from typing import Any


class ScoreCalculator:
    """Calculadora de Score de Seguridad Ponderado (0-100).

    Pondera los hallazgos de las 3 dimensiones:
    - Secrets: 50%
    - IaC: 30%
    - Governance: 20%
    """

    def calculate(
        self,
        secrets_findings: list[dict[str, Any]],
        iac_findings: list[dict[str, Any]],
        governance_findings: list[dict[str, Any]],
    ) -> float:
        """Calcula el score ponderado de seguridad.

        Args:
            secrets_findings: Hallazgos de secretos expuestos.
            iac_findings: Hallazgos de IaC insegura.
            governance_findings: Hallazgos de gobierno.

        Returns:
            Score entre 0 y 100 (acotado con clamp).
        """
        secrets_penalty = self._sum_penalties(secrets_findings)
        iac_penalty = self._sum_penalties(iac_findings)
        gov_penalty = self._sum_penalties(governance_findings)

        raw_score = 100 - (
            secrets_penalty * 0.5 +
            iac_penalty * 0.3 +
            gov_penalty * 0.2
        )

        # Clamp [0, 100]
        return max(0, min(100, raw_score))

    def _sum_penalties(self, findings: list[dict[str, Any]]) -> float:
        """Suma los penalties de una lista de hallazgos."""
        return sum(f.get('penalty', 0) for f in findings)
