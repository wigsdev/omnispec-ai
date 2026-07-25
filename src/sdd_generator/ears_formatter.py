"""EarsFormatter — Validador estricto de patrones EARS.

Detecta y valida los 5 patrones de sintaxis EARS
(Easy Approach to Requirements Syntax) en texto generado.

Attributes:
    PATTERNS: Dict de patrones EARS con sus regex correspondientes.
"""

import re
from enum import Enum


class EarsPattern(Enum):
    """Tipos de patrones EARS soportados."""
    UBIQUITOUS = "ubiquitous"
    EVENT_DRIVEN = "event_driven"
    STATE_DRIVEN = "state_driven"
    UNWANTED = "unwanted"
    OPTIONAL = "optional"


# Regex patterns para cada tipo EARS
EARS_REGEX = {
    EarsPattern.UBIQUITOUS: re.compile(
        r"(?:The|the)\s+system\s+shall\s+",
        re.IGNORECASE
    ),
    EarsPattern.EVENT_DRIVEN: re.compile(
        r"[Ww]hen\s+.+?,\s*(?:the\s+)?system\s+shall\s+",
        re.IGNORECASE
    ),
    EarsPattern.STATE_DRIVEN: re.compile(
        r"[Ww]hile\s+.+?,\s*(?:the\s+)?system\s+shall\s+",
        re.IGNORECASE
    ),
    EarsPattern.UNWANTED: re.compile(
        r"[Ii]f\s+.+?,\s*(?:then\s+)?(?:the\s+)?system\s+shall\s+",
        re.IGNORECASE
    ),
    EarsPattern.OPTIONAL: re.compile(
        r"[Ww]here\s+.+?\s+is\s+supported,\s*(?:the\s+)?system\s+shall\s+",
        re.IGNORECASE
    ),
}


class EarsFormatter:
    """Validador y formateador de patrones EARS.

    Detecta patrones EARS en texto, valida su presencia,
    y puede reformatear texto para cumplir con la sintaxis.
    """

    def validate(self, text: str) -> list[EarsPattern]:
        """Valida qué patrones EARS están presentes en el texto.

        Args:
            text: Texto markdown a validar.

        Returns:
            Lista de patrones EARS encontrados (sin duplicados).
        """
        found_patterns: list[EarsPattern] = []

        for pattern_type, regex in EARS_REGEX.items():
            if regex.search(text):
                found_patterns.append(pattern_type)

        return found_patterns

    def count_requirements(self, text: str) -> int:
        """Cuenta el número total de requisitos EARS en el texto.

        Args:
            text: Texto markdown a analizar.

        Returns:
            Número total de requisitos detectados.
        """
        count = 0
        for regex in EARS_REGEX.values():
            count += len(regex.findall(text))
        return count

    def detect_pattern(self, requirement: str) -> EarsPattern | None:
        """Detecta el patrón EARS de un requisito individual.

        Args:
            requirement: Texto de un requisito individual.

        Returns:
            EarsPattern detectado o None si no coincide con ninguno.
        """
        # Verificar en orden de especificidad (más específico primero)
        check_order = [
            EarsPattern.OPTIONAL,
            EarsPattern.EVENT_DRIVEN,
            EarsPattern.STATE_DRIVEN,
            EarsPattern.UNWANTED,
            EarsPattern.UBIQUITOUS,
        ]

        for pattern_type in check_order:
            if EARS_REGEX[pattern_type].search(requirement):
                return pattern_type

        return None

    def has_minimum_coverage(self, text: str, min_patterns: int = 3) -> bool:
        """Verifica si el texto tiene cobertura mínima de patrones EARS.

        Args:
            text: Texto a verificar.
            min_patterns: Número mínimo de patrones distintos requeridos.

        Returns:
            True si se cumplen al menos min_patterns patrones distintos.
        """
        patterns = self.validate(text)
        return len(patterns) >= min_patterns

    def extract_requirements(self, text: str) -> list[dict[str, str]]:
        """Extrae requisitos individuales con su patrón EARS.

        Args:
            text: Texto markdown con requisitos.

        Returns:
            Lista de dicts con 'text', 'pattern', y 'id' (si se detecta REQ-x.x).
        """
        requirements: list[dict[str, str]] = []
        req_id_pattern = re.compile(r"(REQ-\d+\.\d+)")

        # Buscar líneas que contengan patrones EARS
        lines = text.split("\n")
        for line in lines:
            pattern = self.detect_pattern(line)
            if pattern:
                req_id_match = req_id_pattern.search(line)
                requirements.append({
                    "text": line.strip(),
                    "pattern": pattern.value,
                    "id": req_id_match.group(1) if req_id_match else ""
                })

        return requirements
