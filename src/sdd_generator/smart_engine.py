"""SmartEngine — Motor de fallback local para generación SDD.

Genera un esqueleto SDD usando templates Jinja2 pre-compilados
cuando Gemini Pro no está disponible (API key ausente o rate limit 429).

Latencia objetivo: < 50 ms sin llamadas de red.

Attributes:
    TEMPLATE: Template Jinja2 pre-compilado para SDD esqueleto.
"""

from typing import Any

# Template pre-compilado como string (evita I/O de disco para latencia < 50ms)
_SDD_SKELETON_TEMPLATE = """# SDD — {project_name}

{amb_section}## Requisitos Funcionales (EARS)

| ID | Patrón EARS | Requisito |
|----|-------------|-----------|
| REQ-1.1 | Event-Driven | When the user interacts with the system, the system shall process the request and return a response. |
| REQ-1.2 | Ubiquitous | The system shall validate all inputs before processing. |
| REQ-1.3 | State-Driven | While the system is processing a request, the system shall display a loading indicator. |
| REQ-1.4 | Unwanted | If an error occurs during processing, then the system shall display an error message and log the event. |
| REQ-1.5 | Event-Driven | When the user submits data, the system shall persist it to the database and confirm success. |

## Diagrama de Arquitectura AWS

```mermaid
graph TB
    Client[Cliente Web] --> APIGW[API Gateway]
    APIGW --> Lambda[AWS Lambda<br/>Python 3.11]
    Lambda --> DynamoDB[DynamoDB]
    Lambda --> S3[S3 Bucket]
```

## Matriz de Decisiones

| ID | Aspecto | Clasificación | Riesgo | Acción Recomendada |
|----|---------|---------------|--------|-------------------|
| D-1 | Alcance del proyecto | [AMB] | Medio | Clarificar con stakeholders |
| D-2 | Requisitos de seguridad | [GAP] | Alto | Definir política de autenticación |
| D-3 | Estrategia de escalado | [AMB] | Bajo | Evaluar patrones de tráfico |

## Plan de Tareas

- [ ] Tarea 1: Definir arquitectura serverless AWS (Refs: REQ-1.1)
- [ ] Tarea 2: Implementar validación de inputs (Refs: REQ-1.2)
- [ ] Tarea 3: Configurar manejo de errores centralizado (Refs: REQ-1.4)
- [ ] Tarea 4: Implementar persistencia en DynamoDB (Refs: REQ-1.5)
- [ ] Tarea 5: Agregar tests unitarios con pytest (Refs: REQ-1.1, REQ-1.2)

---

> Generado por OmniSpec AI Smart Engine (modo offline — sin conexión a Gemini Pro).
> Para una especificación completa, configure GEMINI_API_KEY en las variables de entorno.
"""

_AMB_SECTION_TEMPLATE = """## [AMB] Contexto Inferido

> El input proporcionado es breve. Se infiere contexto empresarial estándar.

- **Dominio inferido**: {domain}
- **Entidades inferidas**: Usuarios, Recursos, Transacciones
- **Asunciones**: Sistema web con backend serverless AWS y base de datos NoSQL.

---

"""

# Dominios inferidos según keywords
_DOMAIN_KEYWORDS = {
    "pago": "fintech",
    "pay": "fintech",
    "tienda": "e-commerce",
    "shop": "e-commerce",
    "store": "e-commerce",
    "salud": "healthcare",
    "health": "healthcare",
    "chat": "comunicaciones",
    "mensaje": "comunicaciones",
    "iot": "IoT",
    "sensor": "IoT",
    "clima": "meteorología/SaaS",
    "weather": "meteorología/SaaS",
}


class SmartEngine:
    """Motor de fallback local para generación SDD sin API externa.

    Usa templates pre-compilados en memoria para garantizar
    respuesta en < 50 ms sin I/O de red.
    """

    def generate(self, prompt: str, is_ambiguous: bool = False) -> str:
        """Genera un esqueleto SDD usando templates locales.

        Args:
            prompt: Descripción del proyecto.
            is_ambiguous: Si el prompt fue detectado como vago (< 5 palabras).

        Returns:
            Markdown con SDD esqueleto (EARS, diagrama, matriz, tareas).
        """
        project_name = self._extract_project_name(prompt)
        amb_section = ""

        if is_ambiguous:
            domain = self._infer_domain(prompt)
            amb_section = _AMB_SECTION_TEMPLATE.format(domain=domain)

        return _SDD_SKELETON_TEMPLATE.format(
            project_name=project_name,
            amb_section=amb_section
        )

    def _extract_project_name(self, prompt: str) -> str:
        """Extrae nombre del proyecto del prompt.

        Args:
            prompt: Texto del usuario.

        Returns:
            Nombre corto para el SDD.
        """
        words = prompt.strip().split()
        if not words:
            return "Proyecto Sin Nombre"
        return " ".join(words[:6]).title()

    def _infer_domain(self, prompt: str) -> str:
        """Infiere el dominio de negocio desde el prompt.

        Args:
            prompt: Texto del usuario.

        Returns:
            Nombre del dominio inferido.
        """
        prompt_lower = prompt.lower()
        for keyword, domain in _DOMAIN_KEYWORDS.items():
            if keyword in prompt_lower:
                return domain
        return "SaaS genérico"
