# OmniSpec AI — Stack Tecnológico

## Runtime y Lenguaje

| Componente | Tecnología | Versión |
|------------|-----------|---------|
| Lenguaje | Python | 3.11 |
| Package Manager | pip / pyproject.toml | — |
| Virtual Environment | venv | — |

## IA y LLM

| Componente | Tecnología | Notas |
|------------|-----------|-------|
| Motor principal | Google Gemini Pro | Generación de specs y análisis de código |
| SDK | `google-generativeai` | Cliente oficial de Google |
| Prompts | Templates Jinja2 | Separación de lógica y prompts |

## Backend y API

| Componente | Tecnología | Versión |
|------------|-----------|---------|
| Framework web | Flask | 3.0 |
| Adaptador serverless | serverless-wsgi | — |
| Serialización | JSON nativo | — |
| Validación | marshmallow / pydantic | — |

## Infraestructura (AWS)

| Componente | Tecnología | Notas |
|------------|-----------|-------|
| IaC | AWS CDK (Python) | Definición declarativa de infraestructura |
| Compute | AWS Lambda | Funciones serverless por módulo |
| Base de datos | DynamoDB | NoSQL, pay-per-request |
| API Gateway | AWS API Gateway | Expone endpoints REST |
| Storage | S3 | Almacenamiento de reportes generados |

## Frontend

| Componente | Tecnología | Notas |
|------------|-----------|-------|
| Markup | HTML5 semántico | — |
| Estilos | Vanilla CSS | Tema Neón Dark Mode |
| JavaScript | Vanilla JS (ES6+) | Sin frameworks pesados |
| Fuentes | Google Fonts (monospace) | Estética terminal/hacker |

## Testing

| Componente | Tecnología | Notas |
|------------|-----------|-------|
| Framework | pytest | Obligatorio para todos los módulos |
| Mocking | pytest-mock / unittest.mock | Para APIs externas |
| Cobertura | pytest-cov | Mínimo 80% por módulo |
| Linting | ruff | Fast Python linter |
| Type checking | mypy | Type hints obligatorios |

## Convenciones

- Python style: PEP 8 enforced via `ruff`.
- Type hints en todas las funciones públicas.
- Docstrings formato Google style.
- Variables de entorno para configuración sensible (API keys, endpoints).
- `.env` para desarrollo local, AWS Secrets Manager para producción.
