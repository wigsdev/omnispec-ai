# OmniSpec AI — Definición de Producto

## Visión

OmniSpec AI es una **plataforma agéntica** que automatiza la generación, auditoría y corrección de especificaciones de software usando inteligencia artificial.

---

## Modos de Operación

### 1. SDD Spec Generator

- **Propósito**: Generar especificaciones de diseño de software (SDD) completas a partir de código fuente o descripciones de alto nivel.
- **Sintaxis**: Todas las especificaciones generadas usan formato **EARS** (Easy Approach to Requirements Syntax).
- **Motor IA**: Google Gemini Pro.
- **Input**: Repositorio GitHub, archivos locales o descripción en lenguaje natural.
- **Output**: Documento SDD estructurado con requisitos EARS, diagramas de arquitectura y trazabilidad.

### 2. Auditoría 3D de GitHub

- **Propósito**: Analizar repositorios GitHub en tres dimensiones: estructura, calidad de código y cumplimiento de especificaciones.
- **Permisos**: Solo lectura (read-only) sobre el repositorio objetivo.
- **Dimensiones de auditoría**:
  - **Estructural**: Organización de carpetas, naming conventions, presencia de tests.
  - **Calidad**: Complejidad ciclomática, code smells, cobertura de tests.
  - **Cumplimiento**: Verificación de que el código implementa los requisitos EARS documentados.
- **Output**: Reporte con hallazgos categorizados por severidad (crítico, alto, medio, bajo).

### 3. Auto-Fix con Tests Unitarios

- **Propósito**: Corregir automáticamente los hallazgos de la auditoría generando código y tests unitarios.
- **Permisos**: Escritura — crea Pull Requests con los fixes propuestos.
- **Framework de tests**: pytest obligatorio.
- **Flujo**:
  1. Toma hallazgos de la Auditoría 3D.
  2. Genera fix de código + test unitario que valida la corrección.
  3. Ejecuta `pytest` para verificar que el fix pasa.
  4. Crea Pull Request con descripción del hallazgo, la corrección y evidencia de tests.
- **Seguridad**: Nunca modifica `main` directamente; siempre vía PR para review humano.

---

## Principios de Producto

- **Agéntico**: La plataforma opera de forma autónoma dentro de límites definidos.
- **Trazable**: Cada acción del sistema es auditable y reversible.
- **Seguro**: Principio de mínimo privilegio en todos los accesos.
- **Incremental**: Los modos se pueden usar de forma independiente o en pipeline.
