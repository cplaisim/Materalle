# Ollama Setup Guide

This guide walks through setting up and using Ollama with Materalle-2.

## Quick Start

### 1. Start Ollama Container

```bash
docker run -d \
  --name materalle_ollama \
  -p 11434:11434 \
  -v ollama_data:/root/.ollama \
  -e OLLAMA_HOST=0.0.0.0:11434 \
  ollama/ollama:latest
```

### 2. Pull a Model

```bash
docker exec materalle_ollama ollama pull llama3
# or for a smaller model:
# docker exec materalle_ollama ollama pull mistral
```

### 3. Verify Ollama is Running

```bash
curl http://localhost:11434/api/tags
```

Expected response:
```json
{
  "models": [
    {
      "name": "llama3:latest",
      "modified_at": "2026-09-25T...",
      "size": 4661612160,
      "digest": "..."
    }
  ]
}
```

## Using with Docker Compose

Update `.env`:
```env
LLM_BACKEND=ollama
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3
```

Then start all services:
```bash
docker-compose up -d
```

The Ollama service will start automatically. You can pull models with:
```bash
docker-compose exec ollama ollama pull llama3
```

## Testing the Integration

### Option 1: Via API

```bash
curl -X POST http://localhost:8000/api/v1/test/ollama/ \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello! How are you?"}'
```

### Option 2: Via Django Shell

```bash
python manage.py shell
```

Then:
```python
from materalleapp.agent_base import get_anthropic_response

response = get_anthropic_response(
    messages=[{"role": "user", "content": "What is 2+2?"}],
    system_prompt="You are a helpful math assistant."
)
print(response)
```

### Option 3: Direct HTTP Test

```bash
curl -X POST http://localhost:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3",
    "messages": [
      {"role": "user", "content": "What is 2+2?"}
    ],
    "stream": false
  }'
```

## Available Models

Popular models for Ollama:

| Model | Size | Speed | Quality | Command |
|-------|------|-------|---------|---------|
| llama3 | 4.7GB | Fast | Excellent | `ollama pull llama3` |
| mistral | 5.0GB | Very Fast | Good | `ollama pull mistral` |
| neural-chat | 3.8GB | Very Fast | Good | `ollama pull neural-chat` |
| llama2 | 3.8GB | Fast | Good | `ollama pull llama2` |

## Switching Between Backends

### To use Anthropic Claude:
```env
LLM_BACKEND=anthropic
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### To use Ollama:
```env
LLM_BACKEND=ollama
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3
```

Change the `LLM_BACKEND` value in `.env` and restart the app.

## Troubleshooting

### Ollama won't start
```bash
# Check container logs
docker logs materalle_ollama

# Verify port is available
netstat -an | grep 11434
```

### Model pull times out
- Increase timeout in `docker-compose.yml` healthcheck
- Try a smaller model first (mistral, neural-chat)
- Check internet connection

### Django can't reach Ollama
- When using Docker Compose: use `http://ollama:11434` in DOCKER environment
- When running locally: use `http://localhost:11434`
- Verify: `curl http://ollama:11434/api/tags` from backend container

### Model not found
```bash
# List available models
docker exec materalle_ollama ollama list

# Pull missing model
docker exec materalle_ollama ollama pull llama3
```

## Performance Tips

1. **Use smaller models for development**: `mistral`, `neural-chat` (3-4GB)
2. **Use larger models for production**: `llama3`, `llama2-uncensored` (7-13GB)
3. **Monitor Ollama**: Check logs with `docker logs -f materalle_ollama`
4. **GPU Support**: Add `--gpus all` flag if using NVIDIA GPU:
   ```bash
   docker run -d --gpus all -p 11434:11434 ollama/ollama:latest
   ```

## Environment Variables

- `OLLAMA_HOST`: Set to `0.0.0.0:11434` to listen on all interfaces
- `OLLAMA_MODEL`: Default model to use (e.g., `llama3`)
- `OLLAMA_BASE_URL`: URL to reach Ollama from Django (e.g., `http://ollama:11434`)

## Resources

- [Ollama GitHub](https://github.com/ollama/ollama)
- [Ollama Model Library](https://ollama.ai/library)
- [Ollama API Docs](https://github.com/ollama/ollama/blob/main/docs/api.md)
