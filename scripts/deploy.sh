#!/bin/bash
# ============================================
# OmniSpec AI — Deploy Script
# ============================================
# Uso: ./scripts/deploy.sh [stage]
# Ejemplo: ./scripts/deploy.sh prod

set -euo pipefail

STAGE=${1:-prod}
STACK_NAME="omnispec-ai-${STAGE}"

echo "🚀 Deploying OmniSpec AI (stage: ${STAGE})"
echo "============================================"

# 1. Build container image
echo "📦 Building Lambda container..."
sam build --use-container

# 2. Deploy stack
echo "☁️  Deploying to AWS..."
sam deploy \
  --stack-name "${STACK_NAME}" \
  --no-confirm-changeset \
  --parameter-overrides "Stage=${STAGE}" \
  --capabilities CAPABILITY_IAM \
  --resolve-image-repos \
  --resolve-s3

# 3. Get outputs
echo "📋 Getting stack outputs..."
BUCKET_NAME=$(aws cloudformation describe-stacks \
  --stack-name "${STACK_NAME}" \
  --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue" \
  --output text)

CF_URL=$(aws cloudformation describe-stacks \
  --stack-name "${STACK_NAME}" \
  --query "Stacks[0].Outputs[?OutputKey=='CloudFrontUrl'].OutputValue" \
  --output text)

API_URL=$(aws cloudformation describe-stacks \
  --stack-name "${STACK_NAME}" \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" \
  --output text)

# 4. Sync frontend to S3
echo "🌐 Uploading frontend to S3..."
aws s3 sync frontend/ "s3://${BUCKET_NAME}/" \
  --delete \
  --cache-control "public, max-age=3600"

# 5. Invalidate CloudFront cache
DIST_ID=$(aws cloudfront list-distributions \
  --query "DistributionList.Items[?Comment=='OmniSpec AI - ${STAGE}'].Id" \
  --output text)

if [ -n "${DIST_ID}" ] && [ "${DIST_ID}" != "None" ]; then
  echo "🔄 Invalidating CloudFront cache..."
  aws cloudfront create-invalidation \
    --distribution-id "${DIST_ID}" \
    --paths "/*" > /dev/null
fi

echo ""
echo "============================================"
echo "✅ Deploy complete!"
echo "🌐 URL: ${CF_URL}"
echo "🔌 API: ${API_URL}"
echo "============================================"
