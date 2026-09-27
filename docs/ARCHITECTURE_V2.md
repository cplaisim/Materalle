# Materalle-2 Architecture V2 — AWS-Only, Local-First, Cost-Minimized

**Status:** Proposed — pending approval
**Motivation:** Cut AWS spend (~$100/mo → ~$5/mo) and keep student PII on-premises while still using **only AWS services** in the cloud.

---

## 1. Core Idea

- **Frontend** (Next.js SPA) hosted on S3+CloudFront.
- **Users** live in **Amazon Cognito** (replaces the `User`/`UserProfile` tables in the cloud — Cognito IS the users DB).
- **Student data + everything else** stays in a local Postgres on the daycare computer, served by local Django + Ollama.
- **Bridge between frontend and local backend** uses **API Gateway WebSocket API** — local Django holds a persistent WSS connection to AWS. Frontend calls AWS, AWS relays requests to the local backend over WS, backend responds, AWS routes back to frontend.

No tunnels, no third-party services, no inbound ports on the local machine.

## 2. Topology

```
                     ┌───────────────────────────┐
                     │  S3 + CloudFront          │   Static SPA
                     │  (frontend-web)           │
                     └────────────┬──────────────┘
                                  │ HTTPS
                ┌─────────────────┼──────────────────┐
                │                                    │
                ▼                                    ▼
       ┌──────────────────┐               ┌───────────────────────┐
       │ Amazon Cognito   │               │ API Gateway           │
       │  User Pool       │               │  WebSocket API        │
       │  (users, roles,  │               │   wss://ws.materalle  │
       │   JWTs)          │               └──────┬────────────┬───┘
       └──────────────────┘                      │            │
                                                 │ Lambda     │
                                                 │ ($default, │
                                                 │  $connect, │
                                                 │  request)  │
                                                 ▼            │
                                           ┌───────────┐      │
                                           │ DynamoDB  │      │
                                           │ (connId   │      │
                                           │  routing) │      │
                                           └───────────┘      │
                                                              │ persistent WSS
                                                              │
                                                              ▼
                                                  ┌─────────────────────┐
                                                  │  Daycare computer   │
                                                  │  ──────────────     │
                                                  │  Django backend     │
                                                  │  Postgres (student  │
                                                  │    + sage + grace + │
                                                  │    patience data)   │
                                                  │  Ollama             │
                                                  │  WS client          │
                                                  └─────────────────────┘
```

## 3. AWS Services Used

| Service | Purpose | Monthly Cost (est.) |
|---|---|---|
| **Cognito User Pool** | Auth + user directory + role claim | $0 (free tier: 50k MAU) |
| **S3** | Static frontend + media backups | ~$0.50 |
| **CloudFront** | CDN for SPA | ~$0.50 (free tier 1TB/mo first year) |
| **API Gateway (WebSocket API)** | Bridge to local backend | ~$0.50 |
| **Lambda** | WS route handlers ($connect, $disconnect, request relay) | ~$0 (free tier 1M req) |
| **DynamoDB** | Single table: active backend connections | ~$0 (free tier 25GB) |
| **Route 53** | DNS for materalle.com | $0.50 |
| **ACM** | Certs | $0 |
| **CloudWatch Logs** | Minimal logging | ~$0.50 |
| **Total** | | **~$2.50/mo** |

**Removed:** ECS Fargate, ALB, NAT Gateway, RDS, ElastiCache. All ECS/VPC/RDS torn down post-migration.

## 4. Auth — Cognito Replaces UserProfile/LLMSettings

Cognito User Pool fields:
- Standard: `email`, `preferred_username`, `given_name`, `family_name`, `phone_number`
- **Custom attributes** (prefix `custom:`):
  - `custom:role` — `PARENT` | `CAREGIVER` | `ADMINISTRATOR`
  - `custom:llm_backend` — `anthropic` | `ollama`
  - `custom:ollama_model` — e.g. `llama3`
  - `custom:admin_title`, `custom:admin_department`

### Auth flow

1. Frontend calls Cognito directly via **AWS Amplify Auth** (or `amazon-cognito-identity-js`).
2. Cognito returns `id_token` (JWT) with claims including `custom:role`.
3. Frontend stores tokens, attaches `id_token` to every WS message payload.
4. Lambda relay validates the JWT signature using Cognito's JWKS (cached) before forwarding to the local backend.
5. Local backend trusts the Lambda relay (private AWS-issued signature on the forwarded envelope) and reads `user_id` / `role` from the claims.

**No `auth_user` table exists in the cloud.** The `users` DB is effectively Cognito.

### Settings page

The LLM settings page now **writes directly to Cognito** via `updateUserAttributes`. No server round-trip.

## 5. Local Backend — What Stays, What Goes

### Keep (runs locally)
- `enroll/` (Student, ChildActivity)
- `sage/` (all models)
- `grace/`, `patience/`
- `agent/`
- `website/models.py`: `Document`, `LearningSession`, `Interaction`
- `materalleapp/agent_base.py` — wired exclusively to Ollama now

### Delete from the codebase
- `website/models.py`: `UserProfile`, `LLMSettings`
- `website/views.py`: `register`, `login`, `logout`, `llm_settings`, `toggle_llm_backend` (all replaced by Cognito)
- All Anthropic API code paths (student chat never leaves the machine)

### New
- `materalleapp/ws_client.py` — long-running asyncio task that:
  1. On startup: fetch a short-lived AWS IAM credential via **SigV4** (using a dedicated IAM user for the local device; credentials in `.env.local`), sign a WSS URL, open the connection to API Gateway.
  2. Handle incoming request envelopes → dispatch to Django views via ASGI in-process (using `django.core.handlers.asgi.ASGIHandler`).
  3. Send response envelopes back through the same WS.
  4. Reconnect with exponential backoff on disconnect.
- `materalleapp/cognito_auth.py` — DRF auth class that validates Cognito JWT from the envelope and creates a stub `request.user` with `id`, `username`, `role` attributes.
- `management/commands/run_bridge.py` — entry point that starts Django + the WS client together.

### No inbound ports on the local machine
Local machine makes **outbound** WSS connection only. No port forwarding, no firewall changes, no public IP.

## 6. Bridge Protocol (Envelope Format)

### Request (Frontend → Lambda → Local backend)
```json
{
  "type": "request",
  "request_id": "uuid",
  "method": "POST",
  "path": "/sage/interaction/",
  "headers": {"content-type": "application/json"},
  "body": "...",
  "id_token": "eyJraWQi..."
}
```

### Response (Local backend → Lambda → Frontend)
```json
{
  "type": "response",
  "request_id": "uuid",
  "status": 200,
  "headers": {"content-type": "application/json"},
  "body": "..."
}
```

Streaming (LLM tokens): response envelopes carry `"type": "response_chunk"` with `"final": false`, terminated by `"final": true`.

## 7. Lambda Relay Logic

Three Lambda functions behind the WebSocket API:

### `$connect`
- Identifies who's connecting via a query-string token.
  - Local backend → presents an IAM-signed SigV4 request (API Gateway validates natively via `AWS_IAM` authorizer).
  - Frontend → presents Cognito id_token, validated by a Lambda authorizer.
- Writes `{connection_id, role: "backend"|"frontend", user_id}` to DynamoDB table `ws_connections` with 24h TTL.

### `$disconnect`
- Deletes the row from DynamoDB.

### `$default` (message router)
- Frontend sends a `request` envelope:
  1. Look up the single row where `role = "backend"` in DynamoDB.
  2. Use **API Gateway Management API** `PostToConnection` to push the envelope to that connection ID.
- Backend sends a `response` envelope:
  1. Look up the frontend connection by `user_id` (stored when frontend connected).
  2. `PostToConnection` back to the frontend.

Only one backend connection exists at a time (single daycare). Multi-tenant would need a per-tenant backend registration.

## 8. Frontend Changes

```ts
// frontend-web/src/auth.ts
import { Amplify } from 'aws-amplify';
import { signIn, signUp, getCurrentUser } from 'aws-amplify/auth';

Amplify.configure({
  Auth: {
    Cognito: {
      userPoolId: 'us-east-1_XXX',
      userPoolClientId: 'YYY',
    },
  },
});
```

```ts
// frontend-web/src/api-client.ts
// All API calls go over WebSocket, not REST
const ws = new WebSocket(`wss://ws.materalle.com?id_token=${idToken}`);
const pending = new Map<string, (res: any) => void>();

ws.onmessage = (evt) => {
  const env = JSON.parse(evt.data);
  const cb = pending.get(env.request_id);
  if (cb) { cb(env); pending.delete(env.request_id); }
};

export function apiCall(method: string, path: string, body?: any) {
  return new Promise((resolve) => {
    const request_id = crypto.randomUUID();
    pending.set(request_id, resolve);
    ws.send(JSON.stringify({ type: 'request', request_id, method, path, body, id_token: idToken }));
  });
}
```

For SSR-heavy pages, we either (a) make everything client-rendered since data is private anyway, or (b) skip SSR for authenticated routes.

## 9. Data Migration

1. **Snapshot current RDS** (keep 30 days).
2. **Export users** from `auth_user` + `website_userprofile` to CSV.
3. **Bulk-import users into Cognito** via `AdminCreateUser` API with custom attributes. Users receive a password-reset email (no way to migrate bcrypt hashes into Cognito).
4. **Dump student tables** from RDS → restore into local Postgres:
   - `enroll_*`, `sage_*`, `grace_*`, `patience_*`, `agent_*`
   - `website_document`, `website_learningsession`, `website_interaction`
5. **Rewrite `user_id` foreign keys**: Cognito uses UUIDs (`sub` claim), not integer PKs. Need a mapping table during migration: old `auth_user.id` → new `cognito_sub`. Update all FKs in-place before the local backend goes live.
   - **Decision point**: easier to keep the old integer IDs and store `cognito_sub` as a new column on a local `cached_user` table, keyed by integer. Migration script assigns integers, Cognito hook populates the mapping on first login.
6. **Tear down** RDS, ECS, ALB, NAT Gateway, VPC endpoints.

## 10. Local Deployment

`docker-compose.yml` (runs on daycare machine):
```yaml
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: materalle
      POSTGRES_USER: materalle
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck:
      test: pg_isready -U materalle
      interval: 10s

  ollama:
    image: ollama/ollama
    volumes: [ollama:/root/.ollama]
    deploy:
      resources:
        reservations:
          devices: [{driver: nvidia, count: all, capabilities: [gpu]}]  # optional

  backend:
    build: {context: ., dockerfile: Dockerfile.prod}
    env_file: .env.local
    depends_on:
      db: {condition: service_healthy}
      ollama: {condition: service_started}
    command: python manage.py run_bridge
    restart: unless-stopped

volumes:
  pgdata:
  ollama:
```

Auto-start on boot via `systemd` (Linux) or `launchd` (macOS).

## 11. Security Boundaries

- **Student PII never enters AWS**: only the envelope body traverses Lambda, which holds it in memory for milliseconds and never writes it anywhere. Set Lambda log level to `WARN` and strip bodies before logging.
- **Cognito handles password storage**: no hash migration, no plaintext.
- **IAM credentials on local device**: scoped to a single IAM user with policy allowing only `execute-api:Invoke` on the WebSocket API ARN. Rotated quarterly.
- **WebSocket TLS**: API Gateway provides TLS 1.2+ termination.
- **No inbound ports** on daycare machine — firewall can be fully closed.
- **Admin sites**: local `/admin/` stays (role-restricted, current deployment). Cognito is managed via AWS Console or a small self-service page in the frontend.

## 12. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Daycare machine offline → app unusable | Frontend detects WS disconnect, shows "Backend offline" banner. Login still works (Cognito is independent). |
| Lambda cold starts add latency | Use provisioned concurrency = 1 on the `$default` handler ($~2/mo extra) OR accept ~300ms cold start. |
| WebSocket disconnects drop in-flight requests | Local backend queues responses locally; reconnect triggers replay. |
| Cognito password migration loses users | Force password reset email at first login post-migration. |
| Lambda sees PII in transit | Document and alarm on any CloudWatch log group containing envelope bodies. |
| Single point of failure (one local machine) | Document backup/recovery via nightly `pg_dump` to encrypted S3 bucket. |

## 13. Open Questions

1. **Streaming LLM responses**: Ollama supports streaming, but API Gateway WebSocket message size limit is 32KB and frame rate is not metered for small messages — OK. Confirm acceptable latency.
2. **`django.contrib.sessions`**: no longer useful (Cognito tokens replace sessions). Remove `SessionMiddleware` from local Django or keep for `/admin/`? **Default: keep for admin only.**
3. **Media uploads** (dish photos, documents): store locally in `MEDIA_ROOT`, serve through the bridge. Large files (>100KB) could become a problem over WS — fall back to pre-signed upload flow to a small S3 bucket if needed.
4. **Mobile app** (`frontend-mobile`): same pattern — Cognito auth + WSS bridge. React Native has WebSocket built-in.
5. **Dev environment**: local dev should bypass the bridge (direct Django). Use `USE_BRIDGE=false` env flag.

## 14. Build Sequence

1. [ ] Approve this doc
2. [ ] Create Cognito User Pool with custom attributes (Terraform in `infra/`)
3. [ ] Create WebSocket API + Lambda functions + DynamoDB table (Terraform)
4. [ ] Build `ws_client.py` + bridge management command in local Django
5. [ ] Build `cognito_auth.py` DRF auth class; strip all `UserProfile`/`LLMSettings` code
6. [ ] Frontend: swap auth to Amplify, swap API client to WSS
7. [ ] Data migration scripts
8. [ ] Cutover window: bulk import Cognito users, spin up local Postgres, register backend WS
9. [ ] Smoke tests
10. [ ] Tear down ECS/ALB/NAT/RDS/VPC

## 15. Cost Summary

| Line item | Monthly |
|---|---|
| Cognito (≤50k MAU) | $0 |
| S3 + CloudFront (SPA) | ~$1 |
| API Gateway WebSocket (~10k msgs/day) | ~$0.50 |
| Lambda (~10k invocations/day) | $0 (free tier) |
| DynamoDB | $0 (free tier) |
| Route 53 | $0.50 |
| CloudWatch | $0.50 |
| **Total** | **~$2.50/mo** |

Down from ~$106/mo.
