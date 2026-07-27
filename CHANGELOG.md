# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es/1.1.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

---

## [0.7.0] — 2026-07-27

### Added
- CI/CD Pipeline completo con GitHub Actions.
  - `ci.yml`: ejecuta pytest (197 tests) + ruff + sam validate en cada PR a `main`.
  - `cd.yml`: sam build → sam deploy → s3 sync → CloudFront invalidation en cada merge a `main`.
- Loading spinner en el botón "Crear Pull Request" durante la autenticación OAuth y creación del PR (UX).
- Branch protection en `main`: PR obligatorio, CI debe pasar antes de mergear.
- GitHub Secrets configurados: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`.
- IAM User `omnispec-deployer` con política de mínimo privilegio para deploys automatizados.

### Changed
- Lambda adapter migrado de `serverless-wsgi` a `Mangum` para mejor soporte Flask 3.x + SSE.
- `lambda_handler.py` reescrito con `Mangum(app, lifespan="off")` como handler principal.
- Secrets cargados desde SSM Parameter Store en runtime (no como env vars de Lambda).

### Fixed
- `sam validate` requería región explícita en CI → añadido `--region us-east-1`.

---

## [0.6.0] — 2026-07-27

### Added
- Despliegue completo en AWS: Lambda (contenedor Docker Python 3.12) + API Gateway HTTP + DynamoDB + S3 + CloudFront + SSM.
- Stack SAM `omnispec-ai-prod` en `us-east-1`.
- Frontend servido desde CloudFront CDN: https://d140eqoid6qg8h.cloudfront.net
- API Gateway: https://pbamtxrcw5.execute-api.us-east-1.amazonaws.com/
- `scripts/deploy.sh` y `scripts/setup_ssm_params.sh` para deploy reproducible.
- `Dockerfile` multi-stage con imagen base `public.ecr.aws/lambda/python:3.12`.
- `template.yaml` SAM con `$default` stage (sin prefijo en rutas).

### Fixed
- Dependencia circular CloudFront ↔ FrontendBucketPolicy: eliminado ARN de CloudFront, usando `SourceAccount` en bucket policy.
- Stage `$default` en API Gateway (evita prefijo `/prod` que rompía las rutas Flask).
- SSM secrets cargados via `boto3` en runtime (no soportado como `{{resolve:ssm-secure}}` en Lambda env vars).

---

## [0.4.0] — 2026-07-25

### Added
- Auditor 3D con escaneo progresivo SSE (enumeración → animación por archivo → veredicto final).
- GitHubFetcher para auditar repositorios reales via GitHub REST API v3.
- Sub-tabs de documentos en el SDD Generator (requirements, design, tasks, AGENTS) con preview markdown.
- Firma de IA en cada documento generado (proveedor, modelo, latencia, fecha).
- Botón "Exportar .kiro Pack" genera ZIP con los 4 documentos completos.

### Changed
- AIRouter optimizado con modelos gratuitos: Gemini Flash Lite, Groq Llama 3.3, Qwen 3.6, GPT-OSS 120B.
- Modelo Gemini actualizado de `gemini-1.5-flash` (deprecated) a `gemini-flash-lite-latest`.
- Scanner soporta extensiones `.pem`, `.key`, `.sh` para detección de claves privadas.

### Fixed
- Sanitización de sintaxis Mermaid inválida (`|>` pattern) generada por LLMs.
- `GeminiClient` ya no lee env var cuando se pasa `api_key=""` explícitamente.
- `validator.py` usa `sys.executable` en vez de `python` para subprocess.

---

## [0.3.0] — 2026-07-25

### Added
- UniversalAIRouter multi-proveedor con failover automático (Gemini → Groq → SmartEngine).
- Integración con SDKs: `google-genai`, `groq`.
- Provider badge en la UI mostrando qué IA respondió y latencia.
- Configuración `python-dotenv` para carga de `.env`.

---

## [0.2.0] — 2026-07-25

### Added
- Módulo Auto-Fix Engine (`src/pr_engine/`): generador de diffs, tests pytest, validador, PR creator.
- Protocolo Human-in-the-Loop de Permiso de Escritura con descarga local si se deniega.
- Branch naming con timestamp fallback para evitar colisiones 422.
- Módulo Auditor 3D (`src/auditor/`): scanner, structural (secretos), quality (IaC), compliance (gobierno).
- Protocolo Human-in-the-Loop de Permiso de Lectura.
- Score ponderado (0-100) con clamp y colores semáforo.
- Integración Gemini Role-2 con batching y fallback genérico.
- 142 tests unitarios (auditor + pr_engine).

---

## [0.1.0] — 2026-07-25

### Added
- Backend Flask con SDK Gemini Pro y System Prompt Role-1 (Lead Requirements Engineer).
- Generador SDD EARS con validación de 5 patrones (Ubiquitous, Event-Driven, State-Driven, Optional, Unwanted).
- Smart Engine fallback local (Jinja2 templates, < 50ms).
- SSE streaming con timeout warning a 25s.
- Endpoint export ZIP (Pack .kiro).
- 91 tests unitarios (sdd_generator + api).

---

## [0.0.1] — 2026-07-25

### Added
- Frontend Web UI base neón dark mode con 3 pestañas (SDD Generator, Auditor 3D, Auto-Fix Engine).
- Componentes: TabPanel, PermissionModal, StreamingPanel, MermaidBlock, DiffViewer, ScoreGauge.
- CDN imports: marked.js (markdown), mermaid.js (diagramas).
- Servidor Flask mínimo (`GET /`, `/api/v1/health`).
- 9 tests de UI base.
- Estructura de gobernanza: AGENTS.md, .kiro/steering/, .kiro/specs/app/.
- Especificación SDD EARS completa (requirements, design, tasks) con edge cases.
- .gitignore, .kiroignore, README.md.
