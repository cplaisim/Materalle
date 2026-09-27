# Environment Variables — Materalle-2

## Backend (Django)
| Variable | Description | Required |
|----------|-------------|----------|
| `DJANGO_SECRET_KEY` | Django secret key | Yes |
| `DJANGO_DEBUG` | Debug mode | Yes |
| `DATABASE_URL` | PostgreSQL connection | Yes |
| `REDIS_URL` | Redis connection | Yes |
| `ANTHROPIC_API_KEY` | Claude API key for agents | Yes (if LLM_BACKEND=anthropic) |
| `LLM_BACKEND` | LLM provider: `anthropic` (default) or `ollama` | No |
| `OLLAMA_BASE_URL` | Ollama server URL (default: `http://localhost:11434`) | No |
| `OLLAMA_MODEL` | Ollama model name (default: `llama3`) | No |
| `CORS_ALLOWED_ORIGINS` | Frontend origins | Yes |
| `AWS_S3_BUCKET_NAME` | Media storage | Prod |

## Frontend Web (Next.js)
| Variable | Description | Required |
|----------|-------------|----------|
| `NEXT_PUBLIC_API_URL` | Backend API URL | Yes |
| `NEXT_PUBLIC_APP_URL` | This app's URL | Yes |

## Frontend Mobile (React Native)
| Variable | Description | Required |
|----------|-------------|----------|
| `EXPO_PUBLIC_API_URL` | Backend API URL | Yes |
