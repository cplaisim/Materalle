#!/bin/bash
set -euo pipefail

# ──────────────────────────────────────────────────────────────
# Materalle-2 — Deploy to AWS ECS Fargate
# Usage: ./infra/scripts/deploy.sh [region]
# Prerequisites: aws cli, docker, terraform
# ──────────────────────────────────────────────────────────────

REGION="${1:-us-east-1}"
PROJECT="materalle"
ENV="prod"
PREFIX="${PROJECT}-${ENV}"

echo "==> Deploying Materalle-2 to AWS ($REGION)"

# ── 1. Get ECR repo URL ─────────────────────────────────────
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${PREFIX}-backend"

echo "==> ECR: $ECR_REPO"

# ── 2. Login to ECR ─────────────────────────────────────────
aws ecr get-login-password --region "$REGION" | \
  docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

# ── 3. Build & push Docker image ────────────────────────────
echo "==> Building production image (linux/amd64 for ECS Fargate)..."
docker build --platform linux/amd64 -f Dockerfile.prod -t "${PREFIX}-backend:latest" .

docker tag "${PREFIX}-backend:latest" "${ECR_REPO}:latest"
docker tag "${PREFIX}-backend:latest" "${ECR_REPO}:$(git rev-parse --short HEAD)"

echo "==> Pushing to ECR..."
docker push "${ECR_REPO}:latest"
docker push "${ECR_REPO}:$(git rev-parse --short HEAD)"

# ── 4. Upload static files to S3 ────────────────────────────
STATIC_BUCKET="materalle-prod-static-120569618568-us-east-1-an"
echo "==> Syncing static files to S3..."
docker run --rm "${PREFIX}-backend:latest" python manage.py collectstatic --noinput 2>/dev/null || true
# Create temp container, copy staticfiles out, sync to S3
CONTAINER_ID=$(docker create "${PREFIX}-backend:latest")
docker cp "${CONTAINER_ID}:/app/staticfiles" /tmp/materalle-static
docker rm "$CONTAINER_ID"
aws s3 sync /tmp/materalle-static "s3://${STATIC_BUCKET}/static/" --delete
rm -rf /tmp/materalle-static

# ── 5. Force new ECS deployment ──────────────────────────────
echo "==> Triggering ECS deployment..."
aws ecs update-service \
  --cluster "${PREFIX}-cluster" \
  --service "${PREFIX}-backend" \
  --force-new-deployment \
  --region "$REGION" \
  > /dev/null

echo "==> Waiting for deployment to stabilize..."
aws ecs wait services-stable \
  --cluster "${PREFIX}-cluster" \
  --services "${PREFIX}-backend" \
  --region "$REGION"

# ── 6. Run migrations ───────────────────────────────────────
echo "==> Running database migrations..."
TASK_ARN=$(aws ecs run-task \
  --cluster "${PREFIX}-cluster" \
  --task-definition "${PREFIX}-backend" \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$(aws ecs describe-services --cluster ${PREFIX}-cluster --services ${PREFIX}-backend --query 'services[0].networkConfiguration.awsvpcConfiguration.subnets' --output text | tr '\t' ',')],securityGroups=[$(aws ecs describe-services --cluster ${PREFIX}-cluster --services ${PREFIX}-backend --query 'services[0].networkConfiguration.awsvpcConfiguration.securityGroups' --output text | tr '\t' ',')]}" \
  --overrides '{"containerOverrides":[{"name":"backend","command":["python","manage.py","migrate","--noinput"]}]}' \
  --query 'tasks[0].taskArn' --output text \
  --region "$REGION")

echo "  Migration task: $TASK_ARN"
aws ecs wait tasks-stopped --cluster "${PREFIX}-cluster" --tasks "$TASK_ARN" --region "$REGION"
echo "  Migrations complete."

# ── Done ─────────────────────────────────────────────────────
ALB_DNS=$(aws elbv2 describe-load-balancers \
  --names "${PREFIX}-alb" \
  --query 'LoadBalancers[0].DNSName' --output text \
  --region "$REGION" 2>/dev/null || echo "unknown")

echo ""
echo "==> Deployment complete!"
echo "    API:    http://${ALB_DNS}/api/v1/"
echo "    Admin:  http://${ALB_DNS}/admin/"
echo "    Image:  ${ECR_REPO}:$(git rev-parse --short HEAD)"
