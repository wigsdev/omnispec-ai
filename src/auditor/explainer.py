"""RiskExplainer — Generador de explicaciones contextuales con AIRouter.

Invoca el AIRouter multi-proveedor con System Prompt Role-2
(DevSecOps Security Auditor) para generar explicaciones de riesgo
por hallazgo. Usa batching (hasta 5 findings por llamada).

Fallback: texto genérico si todos los proveedores fallan.
"""

import json
from typing import Any

from src.sdd_generator.ai_router import UniversalAIRouter

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

    Usa AIRouter multi-proveedor con batching para generar explicaciones.
    Fallback genérico si ningún proveedor está disponible.
    """

    def __init__(self, ai_router: UniversalAIRouter | None = None, gemini_client=None):
        """Inicializa el explainer.

        Args:
            ai_router: Router multi-proveedor inyectable.
            gemini_client: Legacy param (backward compat for tests).
        """
        if gemini_client is not None:
            # Backward compatibility: wrap legacy client
            from src.sdd_generator.ai_router import AIProvider, ProviderError
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

            from src.sdd_generator.ai_router import SmartEngineProvider
            self.router = UniversalAIRouter(providers=[
                LegacyProvider(gemini_client),
                SmartEngineProvider(),
            ])
        else:
            self.router = ai_router or UniversalAIRouter()

    def explain_findings(
        self, findings: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Genera explicaciones para una lista de hallazgos.

        Agrupa en batches de BATCH_SIZE y llama al AIRouter.
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
        """Explica un batch de hallazgos con el AIRouter."""
        prompt = self._build_batch_prompt(batch)

        result = self.router.generate(
            prompt=prompt,
            system_prompt=ROLE_2_SYSTEM_PROMPT,
        )

        # Si fue SmartEngine (fallback), retornar genérico
        if result.get("provider") == "SmartEngine":
            return [GENERIC_EXPLANATION] * len(batch)

        return self._parse_explanations(result["content"], len(batch))

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
        """Parsea la respuesta JSON del proveedor."""
        try:
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

            while len(result) < expected_count:
                result.append(GENERIC_EXPLANATION)

            return result

        except (json.JSONDecodeError, KeyError, TypeError):
            return [GENERIC_EXPLANATION] * expected_count
