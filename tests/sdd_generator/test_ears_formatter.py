"""Tests para src/sdd_generator/ears_formatter.py.

Valida el formateador EARS: detección de los 5 patrones,
conteo de requisitos, y extracción con IDs trazables.
"""

import pytest

from src.sdd_generator.ears_formatter import EarsFormatter, EarsPattern


@pytest.fixture
def formatter():
    """Fixture: instancia de EarsFormatter."""
    return EarsFormatter()


class TestEarsValidate:
    """Tests de validate() — detección de patrones presentes."""

    def test_detects_ubiquitous_pattern(self, formatter):
        """Detecta patrón Ubiquitous: 'The system shall...'"""
        text = "The system shall validate all user inputs."
        patterns = formatter.validate(text)
        assert EarsPattern.UBIQUITOUS in patterns

    def test_detects_event_driven_pattern(self, formatter):
        """Detecta patrón Event-Driven: 'When..., the system shall...'"""
        text = "When the user submits a form, the system shall save the data."
        patterns = formatter.validate(text)
        assert EarsPattern.EVENT_DRIVEN in patterns

    def test_detects_state_driven_pattern(self, formatter):
        """Detecta patrón State-Driven: 'While..., the system shall...'"""
        text = "While the system is processing, the system shall display a spinner."
        patterns = formatter.validate(text)
        assert EarsPattern.STATE_DRIVEN in patterns

    def test_detects_unwanted_pattern(self, formatter):
        """Detecta patrón Unwanted: 'If..., then the system shall...'"""
        text = "If an error occurs, then the system shall log the event."
        patterns = formatter.validate(text)
        assert EarsPattern.UNWANTED in patterns

    def test_detects_optional_pattern(self, formatter):
        """Detecta patrón Optional: 'Where... is supported, the system shall...'"""
        text = "Where multi-language is supported, the system shall display content in the user's locale."
        patterns = formatter.validate(text)
        assert EarsPattern.OPTIONAL in patterns

    def test_detects_multiple_patterns(self, formatter):
        """Detecta múltiples patrones en un mismo texto."""
        text = (
            "The system shall validate inputs.\n"
            "When the user clicks submit, the system shall save data.\n"
            "If an error occurs, then the system shall retry."
        )
        patterns = formatter.validate(text)
        assert len(patterns) >= 3
        assert EarsPattern.UBIQUITOUS in patterns
        assert EarsPattern.EVENT_DRIVEN in patterns
        assert EarsPattern.UNWANTED in patterns

    def test_returns_empty_for_no_patterns(self, formatter):
        """Retorna lista vacía si no hay patrones EARS."""
        text = "This is just a regular sentence without any EARS pattern."
        patterns = formatter.validate(text)
        assert patterns == []


class TestEarsCountRequirements:
    """Tests de count_requirements()."""

    def test_counts_single_requirement(self, formatter):
        """Cuenta 1 requisito correctamente."""
        text = "The system shall process payments."
        assert formatter.count_requirements(text) == 1

    def test_counts_multiple_requirements(self, formatter):
        """Cuenta múltiples requisitos."""
        text = (
            "The system shall validate inputs.\n"
            "The system shall log all actions.\n"
            "When user logs in, the system shall create a session."
        )
        assert formatter.count_requirements(text) >= 3

    def test_counts_zero_for_no_requirements(self, formatter):
        """Retorna 0 para texto sin requisitos EARS."""
        text = "Hello world. This is not a requirement."
        assert formatter.count_requirements(text) == 0


class TestEarsDetectPattern:
    """Tests de detect_pattern() — patrón de un requisito individual."""

    @pytest.mark.parametrize("text,expected", [
        ("The system shall validate.", EarsPattern.UBIQUITOUS),
        ("When user clicks, the system shall respond.", EarsPattern.EVENT_DRIVEN),
        ("While loading, the system shall show spinner.", EarsPattern.STATE_DRIVEN),
        ("If error, then the system shall retry.", EarsPattern.UNWANTED),
        ("Where i18n is supported, the system shall translate.", EarsPattern.OPTIONAL),
    ])
    def test_detect_each_pattern(self, formatter, text, expected):
        """Detecta correctamente cada patrón individual."""
        assert formatter.detect_pattern(text) == expected

    def test_detect_returns_none_for_non_ears(self, formatter):
        """Retorna None para texto que no es EARS."""
        assert formatter.detect_pattern("Just a normal sentence.") is None


class TestEarsHasMinimumCoverage:
    """Tests de has_minimum_coverage()."""

    def test_passes_with_3_patterns(self, formatter):
        """Pasa con 3 patrones distintos (default)."""
        text = (
            "The system shall do A.\n"
            "When X, the system shall do B.\n"
            "If Y, then the system shall do C."
        )
        assert formatter.has_minimum_coverage(text) is True

    def test_fails_with_1_pattern(self, formatter):
        """Falla con solo 1 patrón."""
        text = "The system shall do A.\nThe system shall do B."
        assert formatter.has_minimum_coverage(text) is False


class TestEarsExtractRequirements:
    """Tests de extract_requirements()."""

    def test_extracts_with_req_id(self, formatter):
        """Extrae requisitos con ID trazable REQ-x.x."""
        text = "REQ-1.1: When user submits, the system shall save."
        reqs = formatter.extract_requirements(text)
        assert len(reqs) == 1
        assert reqs[0]["id"] == "REQ-1.1"
        assert reqs[0]["pattern"] == "event_driven"

    def test_extracts_without_id(self, formatter):
        """Extrae requisitos sin ID (id queda vacío)."""
        text = "The system shall validate all inputs before processing."
        reqs = formatter.extract_requirements(text)
        assert len(reqs) == 1
        assert reqs[0]["id"] == ""
        assert reqs[0]["pattern"] == "ubiquitous"
