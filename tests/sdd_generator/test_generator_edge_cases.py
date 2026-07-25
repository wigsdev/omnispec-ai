"""Tests de Edge Cases para SDDGenerator (AMB-1).

Verifica el comportamiento con prompts vagos (< 5 palabras):
- No retorna error 400 ni bloqueo.
- Genera SDD con sección [AMB] Contexto Inferido.
- Detecta correctamente prompts ambiguos vs no ambiguos.
"""

import pytest
from unittest.mock import MagicMock

from src.sdd_generator.generator import SDDGenerator
from src.sdd_generator.gemini_client import GeminiClient, MissingAPIKeyError


@pytest.fixture
def generator_with_fallback():
    """Fixture: SDDGenerator que siempre usa fallback (sin API key)."""
    client = MagicMock(spec=GeminiClient)
    client.generate.side_effect = MissingAPIKeyError("No key")
    return SDDGenerator(gemini_client=client)


class TestAMB1VaguePromptUnder5Words:
    """Tests para AMB-1: Prompts con menos de 5 palabras."""

    @pytest.mark.parametrize("prompt", [
        "pagos",
        "hacer pagos",
        "app de clima",
        "chat",
    ])
    def test_vague_prompt_does_not_return_error(self, generator_with_fallback, prompt):
        """AC-AMB-1.1: Inputs de 1-4 palabras NO producen error."""
        result = generator_with_fallback.generate(prompt)
        assert result is not None
        assert "content" in result
        assert len(result["content"]) > 0

    @pytest.mark.parametrize("prompt", [
        "pagos",
        "hacer pagos",
        "app de clima",
        "chat",
    ])
    def test_vague_prompt_marks_ambiguous(self, generator_with_fallback, prompt):
        """Prompts < 5 palabras se detectan como ambiguos."""
        result = generator_with_fallback.generate(prompt)
        assert result["is_ambiguous"] is True

    def test_vague_prompt_includes_amb_section(self, generator_with_fallback):
        """AC-AMB-1.3: Respuesta incluye sección [AMB] Contexto Inferido."""
        result = generator_with_fallback.generate("hacer pagos")
        assert "[AMB] Contexto Inferido" in result["content"]

    def test_vague_prompt_infers_domain(self, generator_with_fallback):
        """El fallback infiere dominio del prompt vago."""
        result = generator_with_fallback.generate("pagos")
        assert "fintech" in result["content"].lower()

    def test_single_word_prompt_generates_sdd(self, generator_with_fallback):
        """Un prompt de 1 palabra genera SDD completo."""
        result = generator_with_fallback.generate("chat")
        content = result["content"]
        assert "REQ-" in content
        assert "system shall" in content.lower()


class TestAMB1NonAmbiguousPrompts:
    """Tests para prompts normales (>= 5 palabras)."""

    @pytest.mark.parametrize("prompt", [
        "Build a payment processing system for merchants",
        "Create an e-commerce platform with user authentication and inventory management",
        "Develop a real-time chat application with WebSocket",
    ])
    def test_normal_prompt_not_marked_ambiguous(self, prompt):
        """Prompts >= 5 palabras NO se marcan como ambiguos."""
        client = MagicMock(spec=GeminiClient)
        client.generate.side_effect = MissingAPIKeyError("No key")
        gen = SDDGenerator(gemini_client=client)

        result = gen.generate(prompt)
        assert result["is_ambiguous"] is False

    def test_normal_prompt_no_amb_section(self):
        """Prompts normales NO incluyen sección [AMB]."""
        client = MagicMock(spec=GeminiClient)
        client.generate.side_effect = MissingAPIKeyError("No key")
        gen = SDDGenerator(gemini_client=client)

        result = gen.generate("Build a complete payment processing system for online merchants")
        assert "[AMB] Contexto Inferido" not in result["content"]


class TestAMB1BoundaryConditions:
    """Tests de condiciones límite para AMB-1."""

    def test_exactly_5_words_not_ambiguous(self):
        """Exactamente 5 palabras NO es ambiguo."""
        client = MagicMock(spec=GeminiClient)
        client.generate.side_effect = MissingAPIKeyError("No key")
        gen = SDDGenerator(gemini_client=client)

        result = gen.generate("Build a payment processing system")
        assert result["is_ambiguous"] is False

    def test_exactly_4_words_is_ambiguous(self):
        """Exactamente 4 palabras SÍ es ambiguo."""
        client = MagicMock(spec=GeminiClient)
        client.generate.side_effect = MissingAPIKeyError("No key")
        gen = SDDGenerator(gemini_client=client)

        result = gen.generate("Build a payment system")
        assert result["is_ambiguous"] is True

    def test_empty_prompt_is_ambiguous(self):
        """Prompt vacío es ambiguo (no crashea)."""
        client = MagicMock(spec=GeminiClient)
        client.generate.side_effect = MissingAPIKeyError("No key")
        gen = SDDGenerator(gemini_client=client)

        result = gen.generate("")
        assert result["is_ambiguous"] is True
        assert result["content"] is not None
