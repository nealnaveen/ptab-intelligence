#!/bin/bash
# PTAB Intelligence — Full deploy script
# Usage: ./scripts/deploy.sh
set -e

ACCOUNT_ID="604881392797"
REGION="us-east-1"
PROFILE="ptab"
ECR_REPO="ptab-rag"
IMAGE_TAG="latest"
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO}"

echo "=== PTAB Intelligence Deploy ==="
echo ""

# ── Step 1: Terraform init & apply ───────────────────────────────────────────
echo ">>> Running Terraform..."
cd terraform
terraform init
terraform apply \
  -var="pinecone_api_key=$(grep PINECONE_API_KEY ../.env | cut -d= -f2)" \
  -var="anthropic_api_key=$(grep ANTHROPIC_API_KEY ../.env | cut -d= -f2)" \
  -auto-approve
cd ..

# ── Step 2: Build & push Lambda container ────────────────────────────────────
echo ""
echo ">>> Authenticating with ECR..."
aws ecr get-login-password --region $REGION --profile $PROFILE \
  | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

echo ">>> Building Docker image..."
docker build -t ${ECR_REPO}:${IMAGE_TAG} ./src/retrieval

echo ">>> Pushing to ECR..."
docker tag ${ECR_REPO}:${IMAGE_TAG} ${ECR_URI}:${IMAGE_TAG}
docker push ${ECR_URI}:${IMAGE_TAG}

# ── Step 3: Update Lambda with new image ─────────────────────────────────────
echo ""
echo ">>> Updating Lambda function..."
aws lambda update-function-code \
  --function-name ptab-rag-query \
  --image-uri ${ECR_URI}:${IMAGE_TAG} \
  --profile $PROFILE \
  --region $REGION

aws lambda wait function-updated \
  --function-name ptab-rag-query \
  --profile $PROFILE \
  --region $REGION

# ── Step 4: Print API URL ─────────────────────────────────────────────────────
echo ""
API_URL=$(cd terraform && terraform output -raw api_gateway_url)
echo "=== Deploy complete ==="
echo "  API endpoint: ${API_URL}/query"
echo ""
echo "Test it:"
echo "  curl -X POST ${API_URL}/query \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"question\": \"What are the grounds for inter partes review?\"}'"
