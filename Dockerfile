# ============================================
# OmniSpec AI — Container Lambda (Multi-Stage)
# ============================================

# Stage 1: Builder — instala dependencias
FROM public.ecr.aws/lambda/python:3.12 AS builder

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -t /opt/python/

# Stage 2: Runtime — copia dependencias + código
FROM public.ecr.aws/lambda/python:3.12

# Copiar dependencias instaladas
COPY --from=builder /opt/python/ ${LAMBDA_TASK_ROOT}/

# Copiar código fuente
COPY src/ ${LAMBDA_TASK_ROOT}/src/
COPY frontend/ ${LAMBDA_TASK_ROOT}/frontend/

# Handler de entrada
CMD ["src.api.lambda_handler.handler"]
