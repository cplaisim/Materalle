# API Contract — Materalle-2

> Single source of truth for all API endpoints.
> Updated by the `backend` agent. Consumed by `frontend-web` and `frontend-mobile`.

## Base URL
- Development: `http://localhost:8000/api/v1`
- Staging: `https://api.staging.materalle.com/api/v1`
- Production: `https://api.materalle.com/api/v1`

## Authentication
```
Authorization: Bearer <access_token>
```

### Auth Endpoints
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/auth/register/` | Create parent account | Public |
| POST | `/auth/login/` | Get JWT tokens | Public |
| POST | `/auth/refresh/` | Refresh access token | Public |
| GET | `/auth/me/` | Current user profile | Required |

### Agent Endpoints
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/agents/grace/chat/` | Chat with Grace | Required |
| POST | `/agents/patience/chat/` | Chat with Patience | Required |
| POST | `/agents/sagesse/chat/` | Chat with Sagesse | Required |
| GET | `/sessions/` | List learning sessions | Required |
| GET | `/sessions/<id>/` | Session detail with interactions | Required |

### Response Envelope
```json
{
  "status": "success" | "error",
  "data": { ... },
  "message": "...",
  "errors": null,
  "meta": { "page": 1, "per_page": 20, "total": 100 }
}
```
