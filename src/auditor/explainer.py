"""RiskExplainer — Generador de explicaciones contextuales con Gemini Role-2.

Invoca Gemini Pro con System Prompt Role-2 (DevSecOps Security Auditor)
para generar explicaciones de riesgo por hallazgo. Usa batching (hasta 5
findings por llamada) para reducir latencia y riesgo de rate limit.

Fallback: texto genérico si Gemini retorna 429 o no está disponible.
"""

import json
from typing import Any

from src.sdd_generator.gemini_client import (
    GeminiClient,
    MissingAPIKeyError,
    RateLimitError,
    GeminiClientError,
)

ROLE_2_SYSTEM_PROMPT = """You are a DevSecOps Security Auditor. For each security finding provided,
generate a JSON response with exactly these fields:

{
  "explanations": [
    {
      "finding_index": 0,
      "risk_description": "Brief description of the security risk",
      "impact": "Potential business impact if exploited",
      "remediation": "Specific actionable fix (file + change)"
    }
  ]
}

Rules:
- Return ONLY valid JSON, no markdown fences, no preamble.
- Language: Match the input language (Spanish if findings are in Spanish).
- Be specific: reference the exact file and line from the finding.
- Be accessible: explain in terms understandable without deep security expertise.
"""

GENERIC_EXPLANATION = {
    "risk_description": "Riesgo de seguridad detectado en la configuración.",
    "impact": "Posible exposición de datos o acceso no autorizado.",
    "remediation": "Revise la configuración indicada y aplique el principio de mínimo privilegio.",
}

BATCH_SIZE = 5


class RiskExplainer:
    """Generador de explicaciones contextuales de riesgo.

    Usa Gemini Pro Role-2 con batching para generar explicaciones.
    Fallback genérico si Gemini no está disponible o retorna 429.
    """

    def __init__(self, gemini_client: GeminiClient | None = None):
        """Inicializa el explainer.

        Args:
            gemini_client: Cliente Gemini inyectable. Si None, crea uno.
        """
        self.gemini = gemini_client or GeminiClient()

    def explain_findings(
        self, findings: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Genera explicaciones para una lista de hallazgos.

        Agrupa en batches de BATCH_SIZE y llama a Gemini.
        Si falla, usa explicaciones genéricas.

        Args:
            findings: Lista de hallazgos del scanner.

        Returns:
            Lista de hallazgos enriquecidos con 'explanation'.
        """
        if not findings:
            return findings

        enriched = []
        for i in range(0, len(findings), BATCH_SIZE):
            batch = findings[i:i + BATCH_SIZE]
            explanations = self._explain_batch(batch)

            for j, finding in enumerate(batch):
                explanation = explanations[j] if j < len(explanations) else GENERIC_EXPLANATION
                enriched_finding = {**finding, "explanation": explanation}
                enriched.append(enriched_finding)

        return enriched

    def _explain_batch(
        self, batch: list[dict[str, Any]]
    ) -> list[dict[str, str]]:
        """Explica un batch de hallazgos con Gemini Pro.

        Args:
            batch: Lista de hasta BATCH_SIZE hallazgos.

        Returns:
            Lista de explicaciones (o genéricas si falla).
        """
        if not self.gemini.is_available:
            return [GENERIC_EXPLANATION] * len(batch)

        prompt = self._build_batch_prompt(batch)

        try:
            result = self.gemini.generate(
                prompt=prompt,
                system_prompt=ROLE_2_SYSTEM_PROMPT,
            )
            return self._parse_explanations(result["content"], len(batch))

        except (MissingAPIKeyError, RateLimitError, GeminiClientError):
            return [GENERIC_EXPLANATION] * len(batch)

    def _build_batch_prompt(self, batch: list[dict[str, Any]]) -> str:
        """Construye el prompt con el batch de findings."""
        findings_text = []
        for i, f in enumerate(batch):
            findings_text.append(
                f"Finding {i}: file={f.get('file', '?')}, "
                f"line={f.get('line', '?')}, "
                f"type={f.get('type', '?')}, "
                f"severity={f.get('severity', '?')}, "
                f"description={f.get('description', '?')}"
            )
        return "Explain these security findings:\n" + "\n".join(findings_text)

    def _parse_explanations(
        self, content: str, expected_count: int
    ) -> list[dict[str, str]]:
        """Parsea la respuesta JSON de Gemini.

        Args:
            content: Texto de respuesta de Gemini.
            expected_count: Número esperado de explicaciones.

        Returns:
            Lista de explicaciones parseadas o genéricas si falla el parse.
        """
        try:
            # Limpiar posibles code fences
            clean = content.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1]
                clean = clean.rsplit("```", 1)[0]

            data = json.loads(clean)
            explanations = data.get("explanations", [])

            result = []
            for exp in explanations:
                result.append({
                    "risk_description": exp.get("risk_description", GENERIC_EXPLANATION["risk_description"]),
                    "impact": exp.get("impact", GENERIC_EXPLANATION["impact"]),
                    "remediation": exp.get("remediation", GENERIC_EXPLANATION["remediation"]),
                })

            # Rellenar si faltan
            while len(result) < expected_count:
                result.append(GENERIC_EXPLANATION)

            return result

        except (json.JSONDecodeError, KeyError, TypeError):
            return [GENERIC_EXPLANATION] * expected_count
