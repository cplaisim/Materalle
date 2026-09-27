#!/bin/bash
# Initialize Ollama with model

set -e

OLLAMA_MODEL=${OLLAMA_MODEL:-llama3}
OLLAMA_BASE_URL=${OLLAMA_BASE_URL:-http://ollama:11434}

echo "Waiting for Ollama to be ready..."
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
  if curl -sf "$OLLAMA_BASE_URL/api/tags" > /dev/null 2>&1; then
    echo "✅ Ollama is ready!"
    break
  fi
  attempt=$((attempt + 1))
  echo "Attempt $attempt/$max_attempts - Ollama not ready yet..."
  sleep 2
done

if [ $attempt -eq $max_attempts ]; then
  echo "❌ Ollama failed to start after $max_attempts attempts"
  exit 1
fi

echo "Checking if $OLLAMA_MODEL is installed..."
if ! curl -s "$OLLAMA_BASE_URL/api/tags" | grep -q "$OLLAMA_MODEL"; then
  echo "📥 Pulling $OLLAMA_MODEL model (this may take a few minutes)..."
  curl -X POST "$OLLAMA_BASE_URL/api/pull" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"$OLLAMA_MODEL\"}" \
    -s
  echo "✅ Model pulled successfully!"
else
  echo "✅ $OLLAMA_MODEL model is already installed"
fi

echo "Ollama is ready to use!"
