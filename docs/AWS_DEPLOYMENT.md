# Materalle-2 — AWS Deployment Guide (Console)

Step-by-step instructions for deploying via the AWS Management Console.

---

## Architecture

```
  User → CloudFront (CDN) → S3 (static files)
    ↓
  Route 53 → ALB → ECS Fargate (Django)
                       ↓          ↓
                  RDS PostgreSQL  ElastiCache Redis
```

---

## Step 1: Create an ECR Repository

1. Go to **Amazon ECR** → **Repositories** → **Create repository**
2. Name: `materalle-prod-backend`
3. Scan on push: **Enabled**
4. Click **Create repository**
5. Copy the repository URI (e.g. `123456789.dkr.ecr.us-east-1.amazonaws.com/materalle-prod-backend`)

**Push your image from your local machine:**

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin 123456789.dkr.ecr.us-east-1.amazonaws.com

# Build production image
docker build -f Dockerfile.prod -t materalle-prod-backend .

# Tag and push
docker tag materalle-prod-backend:latest 123456789.dkr.ecr.us-east-1.amazonaws.com/materalle-prod-backend:latest
docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/materalle-prod-backend:latest
```

---

## Step 2: Create an S3 Bucket (Static Files)

1. Go to **S3** → **Create bucket**
2. Name: `materalle-prod-static-120569618568-us-east-1-an`
3. Region: `us-east-1`
4. Uncheck **Block all public access** (static files need to be public)
5. Click **Create bucket**
6. Go to the bucket → **Permissions** → **Bucket Policy** → paste:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "PublicReadGetObject",
    "Effect": "Allow",
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::materalle-prod-static-120569618568-us-east-1-an/*"
  }]
}
```

7. Create a second bucket `materalle-prod-media` for user uploads (keep private)

**Upload static files:**

```bash
python manage.py collectstatic --noinput
aws s3 sync staticfiles/ s3://materalle-prod-static-120569618568-us-east-1-an/static/ --delete
```

---

## Step 3: Create RDS PostgreSQL

1. Go to **RDS** → **Create database**
2. Choose **Standard create**
3. Engine: **PostgreSQL 15**
4. Template: **Free tier** (or Production for HA)
5. DB instance identifier: `materalle-prod-db`
6. Master username: `materalle_admin`
7. Master password: (generate and save to Secrets Manager)
8. Instance: `db.t3.micro` ($15/mo)
9. Storage: 20 GB, enable autoscaling to 100 GB
10. VPC: Use default or create a new one
11. **Public access: No** (only accessible from ECS)
12. Create a new security group: `materalle-db-sg`
13. Database name: `materalle_db`
14. Backup retention: 7 days
15. Click **Create database**

Note the **Endpoint** (e.g. `materalle-prod-db.abc123.us-east-1.rds.amazonaws.com`)
materalle-prod-db.ceveoma8sxxr.us-east-1.rds.amazonaws.com"
---

## Step 4: Create ElastiCache Redis

1. Go to **ElastiCache** → **Redis OSS caches** → **Create**
2. Name: `materalle-prod-redis`
3. Node type: `cache.t3.micro` ($13/mo)
4. Number of replicas: 0 (save cost; set 1+ for production)
5. Subnet group: same VPC as RDS
6. Security group: create `materalle-redis-sg` allowing port 6379 from ECS
7. Click **Create**

Note the **Primary Endpoint** (e.g. `materalle-prod-redis.abc123.cache.amazonaws.com`)

---

## Step 5: Store Secrets in Secrets Manager

1. Go to **Secrets Manager** → **Store a new secret**
2. Create these three secrets:

| Secret Name | Value |
|-------------|-------|
| `materalle-prod/db-password` | Your RDS password |
| `materalle-prod/django-secret-key` | Generate: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `materalle-prod/anthropic-api-key` | Your Anthropic API key |

---

## Step 6: Create ECS Cluster

1. Go to **ECS** → **Clusters** → **Create cluster**
2. Name: `materalle-prod-cluster`
3. Infrastructure: **AWS Fargate** (serverless)
4. Click **Create**

---

## Step 7: Create Task Definition

1. Go to **ECS** → **Task definitions** → **Create new task definition**
2. Family: `materalle-prod-backend`
3. Launch type: **Fargate**
4. OS: Linux/ARM64 (cheaper) or Linux/X86_64
5. CPU: 0.5 vCPU, Memory: 1 GB
6. Task role: create `materalle-ecs-task-role` (needs S3 read/write)
7. Execution role: create `materalle-ecs-exec-role` (needs ECR pull + Secrets Manager read)

**Container definition:**
- Name: `backend`
- Image URI: `123456789.dkr.ecr.us-east-1.amazonaws.com/materalle-prod-backend:latest`
- Port mappings: 8000 TCP
- Environment variables:

| Key | Value |
|-----|-------|
| `DJANGO_SETTINGS_MODULE` | `materalleapp.settings` |
| `DJANGO_DEBUG` | `0` |
| `DJANGO_ALLOWED_HOSTS` | `*` |
| `DB_HOST` | `materalle-prod-db.abc123.us-east-1.rds.amazonaws.com` |
| `DB_PORT` | `5432` |
| `DB_NAME` | `materalle_db` |
| `DB_USER` | `materalle_admin` |
| `REDIS_URL` | `redis://materalle-prod-redis.abc123.cache.amazonaws.com:6379/0` |
| `AWS_STORAGE_BUCKET_NAME` | `materalle-prod-static-120569618568-us-east-1-an` |

- Secrets (from Secrets Manager):

| Key | ValueFrom |
|-----|-----------|
| `DB_PASSWORD` | `arn:aws:secretsmanager:us-east-1:123456789:secret:materalle-prod/db-password` |
| `DJANGO_SECRET_KEY` | `arn:aws:secretsmanager:us-east-1:123456789:secret:materalle-prod/django-secret-key` |
| `ANTHROPIC_API_KEY` | `arn:aws:secretsmanager:us-east-1:123456789:secret:materalle-prod/anthropic-api-key` |

- Log configuration: **awslogs** → log group `/ecs/materalle-prod-backend`

8. Click **Create**

---

## Step 8: Create Application Load Balancer

1. Go to **EC2** → **Load Balancers** → **Create** → **Application Load Balancer**
2. Name: `materalle-prod-alb`
3. Scheme: Internet-facing
4. Listeners: HTTP:80 (add HTTPS:443 later with ACM certificate)
5. Availability Zones: select at least 2
6. Security group: create `materalle-alb-sg` allowing ports 80 and 443

**Create target group:**
1. Target type: **IP addresses**
2. Name: `materalle-prod-backend-tg`
3. Protocol: HTTP, Port: 8000
4. Health check path: `/api/v1/`
5. Register targets: skip (ECS will register automatically)

Set the ALB listener to forward to this target group.

---

## Step 9: Create ECS Service

1. Go to **ECS** → your cluster → **Create service**
2. Launch type: **Fargate**
3. Task definition: `materalle-prod-backend`
4. Service name: `materalle-prod-backend`
5. Desired tasks: 1 (scale up later)
6. Networking: select private subnets, assign the `materalle-ecs-sg` security group
7. Load balancing: select the ALB and target group from Step 8
8. Click **Create service**

---

## Step 10: Run Migrations

Run a one-off task to apply database migrations:

```bash
aws ecs run-task \
  --cluster materalle-prod-cluster \
  --task-definition materalle-prod-backend \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx]}" \
  --overrides '{"containerOverrides":[{"name":"backend","command":["python","manage.py","migrate","--noinput"]}]}'
```

Or use the **ECS Console** → Cluster → **Run new task** → override the command to:
```
python,manage.py,migrate,--noinput
```

---

## Step 11: Create Superuser

Same approach as migrations, override command:
```
python,manage.py,createsuperuser,--noinput,--username,admin,--email,admin@materalle.com
```

Set the `DJANGO_SUPERUSER_PASSWORD` env var in the override.

---

## Step 12: (Optional) CloudFront CDN

1. Go to **CloudFront** → **Create distribution**
2. Origin domain: `materalle-prod-static-120569618568-us-east-1-an.s3.us-east-1.amazonaws.com`
3. Viewer protocol policy: **Redirect HTTP to HTTPS**
4. Cache policy: **CachingOptimized**
5. Click **Create distribution**
6. Update Django `STATIC_URL` to use the CloudFront domain

---

## Step 13: (Optional) Custom Domain

1. Go to **Route 53** → Create hosted zone for your domain
2. Go to **ACM** (Certificate Manager) → Request a public certificate
3. Add the certificate to your ALB listener (HTTPS:443)
4. Create A record (alias) pointing to the ALB

---

## Security Group Rules Summary

| SG Name | Inbound | From |
|---------|---------|------|
| `materalle-alb-sg` | 80, 443 | 0.0.0.0/0 |
| `materalle-ecs-sg` | 8000 | `materalle-alb-sg` |
| `materalle-db-sg` | 5432 | `materalle-ecs-sg` |
| `materalle-redis-sg` | 6379 | `materalle-ecs-sg` |

---

## Estimated Monthly Cost

| Service | Config | Cost |
|---------|--------|------|
| ECS Fargate | 0.5 vCPU, 1 GB | ~$15 |
| RDS PostgreSQL | db.t3.micro | ~$15 |
| ElastiCache Redis | cache.t3.micro | ~$13 |
| S3 + CloudFront | <10 GB | ~$2 |
| ALB | 1 LB | ~$16 |
| NAT Gateway | 1 | ~$32 |
| Secrets Manager | 3 secrets | ~$1 |
| **Total** | | **~$94/mo** |

**Cost saving tip:** Skip NAT Gateway in dev by putting ECS in public subnets with `assign_public_ip = true`. Saves ~$32/mo.

---

## Redeployment

After making code changes:

```bash
# Build and push new image
docker build -f Dockerfile.prod -t materalle-prod-backend .
docker tag materalle-prod-backend:latest 123456789.dkr.ecr.us-east-1.amazonaws.com/materalle-prod-backend:latest
docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/materalle-prod-backend:latest

# Sync static files
python manage.py collectstatic --noinput
aws s3 sync staticfiles/ s3://materalle-prod-static-120569618568-us-east-1-an/static/ --delete

# Force new deployment
aws ecs update-service --cluster materalle-prod-cluster --service materalle-prod-backend --force-new-deployment
```

Or push to `main` branch and let GitHub Actions deploy automatically.

