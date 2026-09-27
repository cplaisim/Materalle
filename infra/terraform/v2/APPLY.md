# V2 Infrastructure — Apply Runbook

Provisions Cognito User Pool + WebSocket bridge (API Gateway + Lambda + DynamoDB) alongside the existing ECS stack. Legacy resources are NOT touched.

## Prerequisites

- AWS CLI authenticated (`aws sts get-caller-identity` works)
- Terraform ≥ 1.5
- Python 3.11 + pip on `$PATH` (the bridge Lambda is packaged locally via `pip install -t`)

## One-time setup

```sh
cd infra/terraform/v2
terraform init
```

## Apply

Use the pre-generated shared secret below (or generate your own with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`). **Save it — the local Django `ws_client.py` will need the same value.**

```sh
export TF_VAR_backend_shared_secret='oLZ3mZUr-SuTNYlkwSDri9fuMQNUHweodChyWNgcx_SU8W3d0RGOl7ik-cuRUF4t'

terraform plan   # sanity check: 18 to add, 0 to destroy
terraform apply  # type yes
```

## Capture outputs

After apply, capture these values — they're needed for the Django + frontend code:

```sh
terraform output -json > /tmp/v2-outputs.json
terraform output v2_cognito_user_pool_id
terraform output v2_cognito_spa_client_id
terraform output v2_ws_endpoint
```

Expected outputs:

| Output | Used by | Goes into |
|---|---|---|
| `v2_cognito_user_pool_id` | Frontend (Amplify), Lambda (JWT verify) | `frontend-web/.env.local`, Lambda env (already set by TF) |
| `v2_cognito_spa_client_id` | Frontend (Amplify), Lambda (aud check) | `frontend-web/.env.local`, Lambda env (already set by TF) |
| `v2_ws_endpoint` | Frontend + local Django | `wss://...` for both WS clients |
| `v2_ws_connections_table` | (info only) | — |
| `v2_backend_ws_secret_arn` | Local Django deploy | Fetched at bridge startup via `aws secretsmanager get-secret-value` OR kept in `.env.local` |

## Smoke tests (post-apply)

### 1. Verify Cognito User Pool

```sh
POOL_ID=$(terraform output -raw v2_cognito_user_pool_id)
aws cognito-idp describe-user-pool --user-pool-id "$POOL_ID" --query 'UserPool.SchemaAttributes[?starts_with(Name, `custom:`)].Name'
```

Should list: `custom:role`, `custom:llm_backend`, `custom:ollama_model`, `custom:admin_title`, `custom:admin_department`.

### 2. Create a test administrator

```sh
POOL_ID=$(terraform output -raw v2_cognito_user_pool_id)
aws cognito-idp admin-create-user \
  --user-pool-id "$POOL_ID" \
  --username admin@materalle.com \
  --user-attributes Name=email,Value=admin@materalle.com Name=email_verified,Value=true Name=custom:role,Value=ADMINISTRATOR Name=custom:llm_backend,Value=ollama \
  --message-action SUPPRESS \
  --temporary-password 'Temp!Pass123'
```

### 3. Verify WebSocket API responds

```sh
WS=$(terraform output -raw v2_ws_endpoint)
echo "$WS"
# Expected: wss://<api-id>.execute-api.us-east-1.amazonaws.com/prod
```

Try a raw connect with `wscat` (install: `npm i -g wscat`):

```sh
wscat -c "$WS?backend_secret=$TF_VAR_backend_shared_secret"
# Should see: "Connected (press CTRL+C to quit)"
# Disconnect with Ctrl+C.
```

Then verify the connection was recorded (and auto-cleaned on disconnect):

```sh
TABLE=$(terraform output -raw v2_ws_connections_table)
aws dynamodb scan --table-name "$TABLE" --max-items 5
```

### 4. Verify Lambda logs

```sh
aws logs tail /aws/lambda/materalle-prod-bridge --since 5m
```

## Rollback

```sh
terraform destroy
```

Safe — only destroys V2 resources. Legacy ECS stack is in a separate state.

## What's next

Once apply succeeds and smoke tests pass, hand back the three output values and I'll wire them into:

1. `materalleapp/cognito_auth.py` (JWT claim reader)
2. `materalleapp/management/commands/run_bridge.py` (outbound WS client)
3. `frontend-web/.env.local` + Amplify config
