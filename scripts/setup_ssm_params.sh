#!/bin/bash
# ============================================
# OmniSpec AI — Setup SSM Parameters
# ============================================
# Uso: ./scripts/setup_ssm_params.sh
#
# Prerequisitos:
#   - AWS CLI configurado con credenciales
#   - Variables de entorno definidas en .env o exportadas
#
# Lee las claves del entorno local y las sube a SSM Parameter Store.

set -euo pipefail

echo "🔐 Setting up SSM Parameters for OmniSpec AI"
echo "============================================"

# Cargar .env si existe
if [ -f .env ]; then
  echo "📄 Loading .env file..."
  set -a
  source .env
  set +a
fi

# Función helper para crear/actualizar parámetro
put_param() {
  local name=$1
  local value=$2
  local type=${3:-SecureString}

  if [ -z "${value}" ]; then
    echo "  ⚠️  SKIP ${name} (empty value)"
    return
  fi

  aws ssm put-parameter \
    --name "${name}" \
    --value "${value}" \
    --type "${type}" \
    --overwrite \
    --no-cli-pager > /dev/null 2>&1

  echo "  ✅ ${name} (${type})"
}

echo ""
echo "Creating parameters..."

# API Keys (SecureString)
put_param "/omnispec/gemini-api-key" "${GEMINI_API_KEY:-}" "SecureString"
put_param "/omnispec/groq-api-key" "${GROQ_API_KEY:-}" "SecureString"

# GitHub OAuth (CLIENT_ID es público, SECRET es seguro)
put_param "/omnispec/github-oauth-client-id" "${GITHUB_OAUTH_CLIENT_ID:-}" "String"
put_param "/omnispec/github-oauth-client-secret" "${GITHUB_OAUTH_CLIENT_SECRET:-}" "SecureString"

# Flask Secret Key
put_param "/omnispec/flask-secret-key" "${FLASK_SECRET_KEY:-}" "SecureString"

echo ""
echo "============================================"
echo "✅ SSM Parameters configured!"
echo ""
echo "Verify with:"
echo "  aws ssm get-parameters-by-path --path /omnispec/ --query 'Parameters[].Name'"
