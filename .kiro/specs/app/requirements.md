# OmniSpec AI — Requirements Specification

> Sintaxis: EARS (Easy Approach to Requirements Syntax)
> Gobernanza: Conforme a `AGENTS.md` — DoD, TDD pytest, trazabilidad obligatoria.

---

## Epic 1: Generador SDD EARS Agéntico (US-1)

### Descripción

Módulo agéntico que genera especificaciones de diseño de software (SDD) completas usando Google Gemini Pro (`gemini-1.5-flash`), produciendo artefactos en sintaxis EARS con diagramas de arquitectura y planes de tareas trazables.

---

### Requisitos Funcionales

#### REQ-1.1 — Generación en Vivo con Gemini Pro (Event-Driven)

> When the user submits a project description or GitHub repository URL in the SDD Generator tab,
> the system shall invoke Google Gemini Pro (`gemini-1.5-flash`) with the System Prompt `Role-1` (Lead Requirements Engineer)
> and stream the generated SDD specification in real-time to the UI.

**Criterios de Aceptación:**

- **AC-1.1.1**: La respuesta de Gemini Pro se renderiza progresivamente en el panel de resultados usando `marked.js`.
- **AC-1.1.2**: El tiempo de primera respuesta visible es inferior a 3 segundos.
- **AC-1.1.3**: Si la API retorna error 429 (Rate Limit), el sistema usa caché DynamoDB como fallback.

---

#### REQ-1.2 — Construcción de User Stories EARS (Ubiquitous)

> The system shall generate all functional requirements using strict EARS syntax patterns
> (Ubiquitous, Event-Driven, State-Driven, Optional, Unwanted Behavior)
> with identifiers trazables (REQ-x.x).

**Criterios de Aceptación:**

- **AC-1.2.1**: Cada requisito generado incluye un patrón EARS identificable.
- **AC-1.2.2**: Los requisitos incluyen identificadores únicos con formato `REQ-<epic>.<secuencia>`.
- **AC-1.2.3**: Se genera un mínimo de 5 requisitos funcionales por especificación.

---

#### REQ-1.3 — Diagrama AWS Mermaid.js (Event-Driven)

> When the SDD generation completes successfully,
> the system shall produce a Mermaid.js architecture diagram
> depicting the AWS serverless infrastructure (Lambda, API Gateway, DynamoDB, S3).

**Criterios de Aceptación:**

- **AC-1.3.1**: El diagrama Mermaid.js se renderiza inline en el UI usando la librería `mermaid.js`.
- **AC-1.3.2**: El diagrama incluye al menos: API Gateway, Lambda, DynamoDB y S3.
- **AC-1.3.3**: La sintaxis Mermaid generada es válida y parseable sin errores.

---

#### REQ-1.4 — Matriz de Decisiones [AMB]/[GAP] (Ubiquitous)

> The system shall include a Decision Matrix in every generated SDD
> classifying each aspecto técnico como [AMB] (ambigüedad detectada) o [GAP] (vacío de especificación)
> with recommended actions for resolution.

**Criterios de Aceptación:**

- **AC-1.4.1**: La matriz contiene al menos las columnas: ID, Aspecto, Clasificación ([AMB]/[GAP]), Riesgo, Acción Recomendada.
- **AC-1.4.2**: Cada entrada tiene una justificación de clasificación generada por Gemini Pro.

---

#### REQ-1.5 — Plan de Tareas Trazables (Ubiquitous)

> The system shall generate a sequential task plan
> where each task is linked to one or more EARS requirements via identifier (REQ-x.x)
> ensuring full traceability between specification and implementation.

**Criterios de Aceptación:**

- **AC-1.5.1**: Cada tarea referencia al menos un `REQ-x.x`.
- **AC-1.5.2**: Las tareas usan formato checkbox `[ ]` para tracking de progreso.
- **AC-1.5.3**: El orden de tareas respeta dependencias lógicas (no se puede testear antes de implementar).

---

#### REQ-1.6 — Exportación Pack `.kiro` (Event-Driven)

> When the user clicks the "Export .kiro Pack" button,
> the system shall generate a ZIP archive containing the SDD specification,
> diagrams Mermaid, task plan, and a pre-configured `AGENTS.md` file.

**Criterios de Aceptación:**

- **AC-1.6.1**: El ZIP contiene: `requirements.md`, `design.md`, `tasks.md`, `AGENTS.md`.
- **AC-1.6.2**: El archivo se descarga automáticamente al navegador del usuario.
- **AC-1.6.3**: El `AGENTS.md` incluido contiene DoD y reglas TDD adaptadas al proyecto generado.

---

## Epic 2: Auditor 3D de Repositorios GitHub (US-2)

### Descripción

Módulo de auditoría tridimensional que inspecciona repositorios GitHub con un protocolo de seguridad Human-in-the-Loop, evaluando secretos expuestos, configuraciones IaC AWS inseguras y gobierno de recursos.

---

### Requisitos Funcionales

#### REQ-2.1 — Protocolo Human-in-the-Loop: Permiso de Lectura (Event-Driven + Unwanted)

> When the user submits a GitHub repository URL for audit,
> the system shall display an explicit permission request dialog
> requiring the user to confirm "Conceder Permiso de Lectura" before proceeding.

> If the user denies the read permission,
> then the system shall abort the audit process immediately
> and display a message confirming that no data was accessed.

**Criterios de Aceptación:**

- **AC-2.1.1**: El modal de permiso muestra claramente: repo URL, scope de acceso (lectura), y datos que serán analizados.
- **AC-2.1.2**: Sin confirmación explícita, el sistema NO realiza ninguna llamada a la API de GitHub.
- **AC-2.1.3**: El estado del permiso se loguea para auditoría (`permission_granted: true/false`, timestamp).

---

#### REQ-2.2 — Inspección de Secretos Expuestos (State-Driven)

> While the audit is in progress with read permission granted,
> the system shall scan all repository files for exposed secrets
> including AWS access keys, passwords, API tokens, and private keys
> using regex patterns and entropy analysis.

**Criterios de Aceptación:**

- **AC-2.2.1**: Detecta patrones: `AKIA[0-9A-Z]{16}` (AWS keys), `password\s*=\s*['"].+['"]`, tokens Bearer/JWT.
- **AC-2.2.2**: Cada hallazgo incluye: archivo, línea, tipo de secreto, severidad (crítica).
- **AC-2.2.3**: No se almacenan ni transmiten los valores de los secretos encontrados, solo metadata.

---

#### REQ-2.3 — Inspección IaC AWS (State-Driven)

> While the audit is in progress with read permission granted,
> the system shall analyze Infrastructure-as-Code files (CloudFormation, CDK, Terraform)
> identifying insecure configurations including overly permissive IAM policies (`Action: "*"`)
> and open Security Groups (`0.0.0.0/0`).

**Criterios de Aceptación:**

- **AC-2.3.1**: Detecta políticas IAM con `Action: "*"` o `Resource: "*"`.
- **AC-2.3.2**: Detecta Security Groups con ingress `0.0.0.0/0` en puertos sensibles (22, 3389, 3306).
- **AC-2.3.3**: Cada hallazgo incluye referencia CIS Benchmark o AWS Well-Architected Framework.

---

#### REQ-2.4 — Inspección de Gobierno (State-Driven)

> While the audit is in progress with read permission granted,
> the system shall verify governance compliance
> checking for required resource tags, naming conventions, and documentation presence.

**Criterios de Aceptación:**

- **AC-2.4.1**: Verifica presencia de tags obligatorios: `Environment`, `Owner`, `Project`, `CostCenter`.
- **AC-2.4.2**: Valida naming conventions contra patrón configurable.
- **AC-2.4.3**: Verifica existencia de `README.md`, `CHANGELOG.md`, y estructura de tests.

---

#### REQ-2.5 — Score de Seguridad Ponderado (Event-Driven)

> When the three-dimensional inspection completes,
> the system shall calculate a weighted Security Score (0 to 100)
> where Secrets = 50% weight, IaC = 30% weight, Governance = 20% weight.

**Criterios de Aceptación:**

- **AC-2.5.1**: Score 0-100 con fórmula: `Score = 100 - (secrets_penalty * 0.5 + iac_penalty * 0.3 + gov_penalty * 0.2)`.
- **AC-2.5.2**: Cada hallazgo tiene un penalty value predefinido por severidad (crítico=20, alto=10, medio=5, bajo=2).
- **AC-2.5.3**: El score se presenta con indicador visual (rojo <40, naranja 40-70, verde >70).

---

#### REQ-2.6 — Explicaciones Contextuales de Riesgo (Event-Driven)

> When a security finding is identified,
> the system shall invoke Gemini Pro with System Prompt `Role-2` (DevSecOps Security Auditor)
> to generate a contextual risk explanation and remediation guidance.

**Criterios de Aceptación:**

- **AC-2.6.1**: Cada hallazgo incluye: descripción del riesgo, impacto potencial, y remediación sugerida.
- **AC-2.6.2**: Las explicaciones están contextualizadas al archivo y línea específica.
- **AC-2.6.3**: El lenguaje es comprensible para desarrolladores sin expertise en seguridad.

---

## Epic 3: Auto-Fix Engine, Testing & Pull Request Generator (US-3)

### Descripción

Motor agéntico que genera parches de código, suites de pruebas unitarias automatizadas, y crea Pull Requests en GitHub tras confirmación explícita del usuario (Human-in-the-Loop con Permiso de Escritura).

---

### Requisitos Funcionales

#### REQ-3.1 — Generación de Parche de Código Diff (Event-Driven)

> When the user selects one or more audit findings for auto-fix,
> the system shall invoke Gemini Pro with System Prompt `Role-3` (Test Automation Engineer)
> and generate a unified diff patch that remediates the selected vulnerabilities.

**Criterios de Aceptación:**

- **AC-3.1.1**: El diff generado es un unified diff válido aplicable con `git apply`.
- **AC-3.1.2**: El diff modifica solo los archivos y líneas necesarios para la remediación.
- **AC-3.1.3**: Se presenta una vista previa del diff con syntax highlighting antes de aplicar.

---

#### REQ-3.2 — Generación de Suite de Tests pytest (Event-Driven)

> When a code patch is generated,
> the system shall simultaneously generate a test file `test_security_patch.py`
> containing pytest unit tests that validate the security fix.

**Criterios de Aceptación:**

- **AC-3.2.1**: El archivo `test_security_patch.py` usa `pytest` con assertions explícitos.
- **AC-3.2.2**: Incluye al menos: test positivo (fix aplicado correctamente) y test negativo (vulnerabilidad ya no existe).
- **AC-3.2.3**: Los tests son ejecutables con `pytest test_security_patch.py --tb=short -q` sin errores de import.

---

#### REQ-3.3 — Protocolo Human-in-the-Loop: Permiso de Escritura (Event-Driven + Unwanted)

> When the diff preview and test suite are displayed to the user,
> the system shall require explicit confirmation of "Conceder Permiso de Escritura"
> before creating any branch or Pull Request on the user's repository.

> If the user denies the write permission,
> then the system shall retain the generated diff and tests for download
> but shall NOT create any branch or Pull Request.

**Criterios de Aceptación:**

- **AC-3.3.1**: El modal muestra: diff completo, tests generados, rama destino (`fix/omnispec-patch`), y repo target.
- **AC-3.3.2**: Sin confirmación explícita, el sistema NO ejecuta ninguna operación de escritura en GitHub.
- **AC-3.3.3**: El usuario puede descargar el diff y tests como archivos locales sin conceder permiso de escritura.
- **AC-3.3.4**: El estado del permiso se loguea para auditoría (`write_permission_granted: true/false`, timestamp).

---

#### REQ-3.4 — Creación de Rama y Pull Request (Event-Driven)

> When the user grants write permission,
> the system shall create a new branch `fix/omnispec-patch` from the default branch,
> apply the generated diff, commit the changes and test file,
> and open a Pull Request via `GitHubClient` with a descriptive body.

**Criterios de Aceptación:**

- **AC-3.4.1**: La rama se crea desde `HEAD` de la rama principal (main/master).
- **AC-3.4.2**: El commit message sigue formato: `fix(security): <descripción breve del hallazgo>`.
- **AC-3.4.3**: El body del PR incluye: hallazgos corregidos, diff aplicado, y resultados de tests.
- **AC-3.4.4**: El PR se crea via API GitHub (`POST /repos/{owner}/{repo}/pulls`) usando `GitHubClient`.

---

#### REQ-3.5 — Validación Pre-PR con pytest (State-Driven)

> While the auto-fix branch is being prepared,
> the system shall execute `pytest test_security_patch.py --tb=short -q`
> and only proceed with the Pull Request if all tests pass.

> If any test fails,
> then the system shall display the test failure output to the user
> and shall NOT create the Pull Request until the issue is resolved.

**Criterios de Aceptación:**

- **AC-3.5.1**: pytest se ejecuta en un entorno aislado antes de crear el PR.
- **AC-3.5.2**: Si los tests fallan, se muestra el output completo de pytest al usuario.
- **AC-3.5.3**: El sistema ofrece regenerar el fix con contexto del error de test.

---

## Matriz de Trazabilidad

| Requisito | Epic | Patrón EARS | Componente | Test Coverage |
|-----------|------|-------------|------------|---------------|
| REQ-1.1 | US-1 | Event-Driven | sdd_generator | test_generator.py |
| REQ-1.2 | US-1 | Ubiquitous | sdd_generator | test_ears_formatter.py |
| REQ-1.3 | US-1 | Event-Driven | sdd_generator | test_generator.py |
| REQ-1.4 | US-1 | Ubiquitous | sdd_generator | test_generator.py |
| REQ-1.5 | US-1 | Ubiquitous | sdd_generator | test_generator.py |
| REQ-1.6 | US-1 | Event-Driven | api/routes | test_routes.py |
| REQ-2.1 | US-2 | Event-Driven + Unwanted | auditor | test_scanner.py |
| REQ-2.2 | US-2 | State-Driven | auditor | test_structural.py |
| REQ-2.3 | US-2 | State-Driven | auditor | test_quality.py |
| REQ-2.4 | US-2 | State-Driven | auditor | test_compliance.py |
| REQ-2.5 | US-2 | Event-Driven | auditor | test_scanner.py |
| REQ-2.6 | US-2 | Event-Driven | auditor | test_scanner.py |
| REQ-3.1 | US-3 | Event-Driven | pr_engine | test_fixer.py |
| REQ-3.2 | US-3 | Event-Driven | pr_engine | test_test_generator.py |
| REQ-3.3 | US-3 | Event-Driven + Unwanted | pr_engine | test_pr_creator.py |
| REQ-3.4 | US-3 | Event-Driven | pr_engine | test_pr_creator.py |
| REQ-3.5 | US-3 | State-Driven | pr_engine | test_validator.py |

---

## 4. Análisis de Ambigüedades, Brechas y Casos Borde

> Clasificación: [AMB] = Ambigüedad detectada | [GAP] = Brecha de especificación | [EDGE] = Caso borde
> Mitigación: Cada hallazgo incluye regla EARS y criterios de aceptación verificables

---

### [AMB-1] Ambigüedad de Prompt Vago

**Problema detectado**: El REQ-1.1 asume que el usuario siempre proporciona una descripción suficiente del proyecto. Sin embargo, inputs mínimos (< 5 palabras, ej. "hacer pagos", "app de clima") carecen de contexto empresarial para generar una especificación SDD significativa.

**Regla de mitigación agéntica (Event-Driven + State-Driven)**:

> When the user submits a project description with fewer than 5 words or lacking business domain context,
> the system shall instruct Gemini Pro (Role-1) to infer a standard enterprise context
> by expanding the input into a business-domain hypothesis before generating the SDD,
> without blocking or rejecting the generation request.

> While generating an SDD from an ambiguous input,
> the system shall prepend a "[AMB] Contexto Inferido" section to the output
> clearly stating the assumptions made by the agent for user validation.

**Criterios de Aceptación:**

- **AC-AMB-1.1**: Inputs de 1-4 palabras NO producen error 400 ni bloqueo; la generación procede.
- **AC-AMB-1.2**: El System Prompt Role-1 incluye instrucción explícita: "Si el input es vago (< 5 palabras), infiere contexto de dominio estándar (e-commerce, fintech, SaaS, etc.) y documenta la inferencia."
- **AC-AMB-1.3**: La respuesta generada incluye sección `[AMB] Contexto Inferido` con las hipótesis expandidas antes de los requisitos EARS.
- **AC-AMB-1.4**: El usuario puede editar o rechazar las inferencias y regenerar con contexto corregido.

**Prompt Enhancement para Role-1:**

```
EXPANSION RULE: If user input contains fewer than 5 words or lacks explicit
business context, apply the following steps:
1. Identify the most probable business domain (e-commerce, fintech, healthcare, SaaS, IoT).
2. Infer standard entities (users, transactions, resources) for that domain.
3. Generate the SDD with a leading [AMB] section documenting all inferences.
4. NEVER reject or return an error for short inputs. Always attempt generation.
```

---

### [GAP-1] Ausencia de API Key de Gemini o Rate Limit (429)

**Problema detectado**: Si `GEMINI_API_KEY` no está configurada, es inválida, o Gemini Pro retorna HTTP 429 (Rate Limit Exceeded), el sistema queda sin capacidad de generación IA. No existe especificación del fallback.

**Regla EARS (Unwanted Behavior + State-Driven)**:

> If the environment variable `GEMINI_API_KEY` is not set or is invalid,
> then the system shall activate the Smart Engine local fallback
> returning a template-based SDD within 50 ms using pre-cached patterns from DynamoDB.

> If Gemini Pro returns HTTP 429 (Rate Limit Exceeded),
> then the system shall query DynamoDB cache for the closest matching cached response
> and serve it with header `X-Cache: STALE` within 50 ms response time.

> While operating in fallback mode (no active Gemini connection),
> the system shall display a visible banner "[MODO OFFLINE] Usando caché local"
> in the UI and log the degradation event for monitoring.

**Criterios de Aceptación:**

- **AC-GAP-1.1**: Con `GEMINI_API_KEY=""` o ausente, la app levanta sin crash y activa fallback en < 50 ms.
- **AC-GAP-1.2**: Con respuesta 429 de Gemini, DynamoDB cache se consulta en < 50 ms y se retorna respuesta stale.
- **AC-GAP-1.3**: La UI muestra banner "[MODO OFFLINE]" con estilo neón naranja cuando está en fallback.
- **AC-GAP-1.4**: Se loguea en `omnispec-audit-log`: `{action_type: "fallback_activated", reason: "missing_key" | "rate_limit_429"}`.
- **AC-GAP-1.5**: El Smart Engine local genera un SDD básico usando templates Jinja2 pre-definidos sin llamar a ninguna API externa.

**Smart Engine Local — Comportamiento:**

| Trigger | Fallback | Latencia Objetivo |
|---------|----------|-------------------|
| `GEMINI_API_KEY` ausente | Template Jinja2 local → SDD genérico | < 50 ms |
| Gemini 429 + cache HIT | DynamoDB stale response | < 50 ms |
| Gemini 429 + cache MISS | Template Jinja2 local → SDD genérico | < 50 ms |
| Gemini 500/502/503 | Retry x1 → si falla → fallback cache/template | < 200 ms |

---

### [GAP-2] Permiso Denegado por Usuario en GitHub

**Problema detectado**: REQ-2.1 y REQ-3.3 definen que sin permiso no se accede a GitHub, pero no especifican el comportamiento completo del UI post-denegación. El usuario no debe quedar en un estado muerto.

**Regla EARS (Unwanted Behavior)**:

> If the user denies the Read Permission in the Auditor 3D tab,
> then the system shall dismiss the permission modal,
> display an informational alert "Auditoría cancelada — No se accedió a ningún dato del repositorio",
> and return the user to the input state with the repository URL preserved for retry.

> If the user denies the Write Permission in the Auto-Fix tab,
> then the system shall dismiss the permission modal,
> display an informational alert "Pull Request cancelado — Los archivos generados están disponibles para descarga local",
> enable download buttons for the diff file and test file,
> and preserve the generated artifacts in session memory for potential retry.

**Criterios de Aceptación:**

- **AC-GAP-2.1**: Al denegar permiso de lectura, la UI NO queda en estado loading ni muestra spinner infinito.
- **AC-GAP-2.2**: La alerta informativa usa estilo neón naranja (no rojo error) y lenguaje amigable no-culpabilizante.
- **AC-GAP-2.3**: El campo de URL del repositorio mantiene el valor ingresado para facilitar retry sin re-tipeo.
- **AC-GAP-2.4**: Al denegar permiso de escritura, los botones "Descargar Diff" y "Descargar Tests" se activan inmediatamente.
- **AC-GAP-2.5**: Los artefactos generados (diff + tests) persisten en memoria del navegador durante la sesión activa.
- **AC-GAP-2.6**: Se loguea: `{action_type: "permission_denied", scope: "read" | "write", repo_url: "..."}`.

---

### [EDGE-1] Timeout de API Gateway (29s)

**Problema detectado**: AWS API Gateway tiene un hard limit de 29 segundos para respuestas síncronas. Generaciones complejas de Gemini Pro (especialmente con repos grandes en Role-2) pueden exceder este límite.

**Regla EARS (State-Driven + Unwanted Behavior)**:

> While a Gemini Pro generation is in progress,
> the system shall stream partial responses via Server-Sent Events (SSE)
> sending incremental chunks every 5 seconds to maintain the API Gateway connection alive.

> If the generation exceeds 25 seconds without completion,
> then the system shall send a final SSE event `{type: "timeout_warning", elapsed: 25}`
> and the client JavaScript shall prepare for graceful degradation.

> If the API Gateway connection is lost (timeout at 29s),
> then the client shall invoke AbortController.abort() on the fetch request,
> display a message "Generación interrumpida — Resultado parcial disponible",
> and render whatever partial response was received via SSE.

**Criterios de Aceptación:**

- **AC-EDGE-1.1**: El endpoint usa `Content-Type: text/event-stream` para streaming SSE.
- **AC-EDGE-1.2**: Chunks parciales se envían cada ≤ 5 segundos para evitar timeout de API Gateway.
- **AC-EDGE-1.3**: El cliente JavaScript implementa `AbortController` con timeout configurable (default: 28s).
- **AC-EDGE-1.4**: Respuestas parciales se renderizan con `marked.js` — el usuario ve progreso incremental.
- **AC-EDGE-1.5**: Al abortar, la UI muestra resultado parcial + botón "Reintentar" para completar la generación.
- **AC-EDGE-1.6**: El backend Flask usa `Response(stream_with_context(generate()), mimetype='text/event-stream')`.

**Estrategia de Streaming:**

```
Client                    API GW (29s limit)           Lambda + Flask
  |--- GET /api/v1/generate (Accept: text/event-stream) --->|
  |                                                          |--- Gemini Pro call
  |<--- SSE: {type: "chunk", data: "## Requisitos..."} -----|    (streaming)
  |<--- SSE: {type: "chunk", data: "REQ-1.1..."} -----------|    (cada 5s)
  |<--- SSE: {type: "chunk", data: "```mermaid..."} --------|
  |                                                          |
  |  [IF elapsed > 25s]                                      |
  |<--- SSE: {type: "timeout_warning", elapsed: 25} --------|
  |                                                          |
  |  [IF elapsed > 28s — client AbortController fires]       |
  |--- AbortController.abort() --->|                         |
  |                                                          |
  |  [Render partial with marked.js + show "Reintentar"]     |
```

---

### [EDGE-2] Repositorio Vacío o Formatos No Soportados

**Problema detectado**: REQ-2.2/2.3/2.4 asumen que el repositorio contiene archivos analizables. No se especifica el comportamiento para repos vacíos, repos con solo binarios, o archivos que exceden límites de tamaño.

**Regla EARS (Unwanted Behavior + Event-Driven)**:

> If the submitted GitHub repository contains no supported files (.py, .yaml, .yml, .json, .tf, .template),
> then the system shall return a structured response with score 100 (no findings),
> a message "Repositorio sin archivos analizables en formatos soportados",
> and a list of file extensions found for user reference.

> If any individual file in the repository exceeds 256 KB,
> then the system shall skip that file during analysis,
> log a warning `{file: "path", size_kb: N, reason: "exceeds_256kb_limit"}`,
> and include it in the report under "Archivos Omitidos" with the size and reason.

> When the repository scan completes with zero analyzable files,
> the system shall NOT calculate a security score
> and shall display "N/A — Sin archivos para analizar" in the ScoreGauge component.

**Criterios de Aceptación:**

- **AC-EDGE-2.1**: Repositorios vacíos (0 archivos) retornan 200 OK con body estructurado, NO error 500.
- **AC-EDGE-2.2**: Archivos > 256 KB se omiten del análisis con log explícito en el reporte.
- **AC-EDGE-2.3**: El reporte incluye sección "Archivos Omitidos" si algún archivo fue skippeado.
- **AC-EDGE-2.4**: Formatos soportados: `.py`, `.yaml`, `.yml`, `.json`, `.tf`, `.template`, `.cfg`, `.toml`, `.env`.
- **AC-EDGE-2.5**: La UI muestra el score como "N/A" (gris) cuando no hay archivos analizables.
- **AC-EDGE-2.6**: El sistema informa al usuario qué extensiones tiene el repo para orientar próximos pasos.

---

### Matriz de Trazabilidad — Análisis Extendido

| ID | Tipo | Requisitos Afectados | Módulo | Test Coverage |
|----|------|---------------------|--------|---------------|
| AMB-1 | Ambigüedad | REQ-1.1, REQ-1.2 | sdd_generator | test_generator_edge_cases.py |
| GAP-1 | Brecha | REQ-1.1, REQ-2.6, REQ-3.1 | sdd_generator, api | test_fallback.py |
| GAP-2 | Brecha | REQ-2.1, REQ-3.3 | api/routes, frontend | test_permission_denied.py |
| EDGE-1 | Caso Borde | REQ-1.1, REQ-2.6 | api, sdd_generator | test_streaming_timeout.py |
| EDGE-2 | Caso Borde | REQ-2.2, REQ-2.3, REQ-2.4 | auditor | test_empty_repo.py |
