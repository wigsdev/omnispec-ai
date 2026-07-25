# OmniSpec AI — Estructura del Repositorio

## Arquitectura Modular

```
omnispec-ai/
├── AGENTS.md                   # Gobernanza agéntica y DoD
├── README.md                   # Documentación principal
├── pyproject.toml              # Configuración del proyecto Python
├── requirements.txt            # Dependencias pinned
├── .env.example                # Template de variables de entorno
│
├── src/                        # Código fuente principal
│   ├── __init__.py
│   │
│   ├── sdd_generator/          # Modo 1: Generador de Specs SDD
│   │   ├── __init__.py
│   │   ├── generator.py        # Lógica principal de generación
│   │   ├── ears_formatter.py   # Formateo a sintaxis EARS
│   │   ├── gemini_client.py    # Cliente Google Gemini Pro
│   │   └── templates/          # Templates Jinja2 para prompts
│   │       └── sdd_prompt.j2
│   │
│   ├── auditor/                # Modo 2: Auditoría 3D de GitHub
│   │   ├── __init__.py
│   │   ├── scanner.py          # Escaneo de repositorio
│   │   ├── structural.py       # Análisis estructural
│   │   ├── quality.py          # Análisis de calidad
│   │   ├── compliance.py       # Verificación de cumplimiento EARS
│   │   └── report.py           # Generación de reportes
│   │
│   ├── pr_engine/              # Modo 3: Auto-Fix + Pull Requests
│   │   ├── __init__.py
│   │   ├── fixer.py            # Generación de fixes
│   │   ├── test_generator.py   # Generación de tests unitarios
│   │   ├── pr_creator.py       # Creación de Pull Requests
│   │   └── validator.py        # Validación pre-PR (pytest run)
│   │
│   └── api/                    # Capa API (Flask)
│       ├── __init__.py
│       ├── app.py              # Flask app factory
│       ├── routes/             # Blueprints por módulo
│       │   ├── __init__.py
│       │   ├── generator.py    # Endpoints del SDD Generator
│       │   ├── auditor.py      # Endpoints de Auditoría
│       │   └── fixer.py        # Endpoints del Auto-Fix
│       └── middleware/         # Middlewares comunes
│           ├── __init__.py
│           ├── auth.py         # Autenticación
│           └── error_handler.py # Manejo centralizado de errores
│
├── tests/                      # Tests (espejo de src/)
│   ├── __init__.py
│   ├── conftest.py             # Fixtures compartidas
│   ├── sdd_generator/
│   │   ├── __init__.py
│   │   ├── test_generator.py
│   │   ├── test_ears_formatter.py
│   │   └── test_gemini_client.py
│   ├── auditor/
│   │   ├── __init__.py
│   │   ├── test_scanner.py
│   │   ├── test_structural.py
│   │   ├── test_quality.py
│   │   └── test_compliance.py
│   ├── pr_engine/
│   │   ├── __init__.py
│   │   ├── test_fixer.py
│   │   ├── test_test_generator.py
│   │   └── test_pr_creator.py
│   └── api/
│       ├── __init__.py
│       └── test_routes.py
│
├── infra/                      # Infraestructura como código (AWS CDK)
│   ├── __init__.py
│   ├── app.py                  # CDK App entry point
│   ├── stacks/
│   │   ├── __init__.py
│   │   ├── api_stack.py        # Lambda + API Gateway
│   │   ├── storage_stack.py    # DynamoDB + S3
│   │   └── auth_stack.py       # Cognito / API Keys
│   └── cdk.json                # Configuración CDK
│
├── frontend/                   # Frontend estático
│   ├── index.html
│   ├── css/
│   │   └── neon-dark.css       # Tema Neón Dark Mode
│   └── js/
│       └── app.js              # Lógica cliente
│
└── .kiro/                      # Configuración Kiro
    └── steering/
        ├── product.md          # Definición de producto
        ├── tech.md             # Stack tecnológico
        └── structure.md        # Este archivo
```

## Reglas de Estructura

1. **Separación por dominio**: Cada modo (sdd_generator, auditor, pr_engine) es un módulo independiente.
2. **API como capa fina**: `src/api/` solo orquesta, la lógica vive en los módulos de dominio.
3. **Tests como espejo**: La estructura de `tests/` replica exactamente la de `src/`.
4. **Infra separada**: El código CDK vive en `infra/`, nunca mezclado con lógica de negocio.
5. **Frontend desacoplado**: Archivos estáticos en `frontend/`, servidos desde S3/CloudFront.
6. **Sin lógica en raíz**: La raíz solo contiene configuración y documentación.

## Convenciones de Naming

- Módulos: `snake_case` (e.g., `sdd_generator`)
- Archivos Python: `snake_case.py` (e.g., `gemini_client.py`)
- Clases: `PascalCase` (e.g., `SDDGenerator`)
- Funciones/métodos: `snake_case` (e.g., `generate_spec()`)
- Constantes: `UPPER_SNAKE_CASE` (e.g., `MAX_RETRIES`)
- Tests: `test_<module>_<scenario>.py` o dentro del archivo `test_<function>_<scenario>_<expected>`
