#!/usr/bin/env bash
set -euo pipefail

echo "=== Materalle-2 Development Setup ==="

# Check prerequisites
for cmd in docker; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "ERROR: $cmd is not installed."
    exit 1
  fi
done

# Copy .env if missing
if [ ! -f .env ]; then
  echo "Creating .env from .env.example..."
  cp .env.example .env
  echo "  -> Please edit .env with your actual values (especially ANTHROPIC_API_KEY)."
fi

# Build and start services
echo "Building and starting services..."
docker compose up --build -d

# Wait for database
echo "Waiting for database to be ready..."
until docker compose exec -T db pg_isready -U postgres &>/dev/null; do
  sleep 1
done
echo "  -> Database is ready."

# Run migrations
echo "Running Django migrations..."
docker compose exec -T backend python manage.py migrate

# Prompt for superuser
echo ""
echo "Would you like to create a Django superuser? (y/n)"
read -r answer
if [ "$answer" = "y" ]; then
  docker compose exec backend python manage.py createsuperuser
fi

echo ""
echo "=== Setup Complete ==="
echo "  Backend:  http://localhost:8000"
echo "  API:      http://localhost:8000/api/v1/"
echo "  Frontend: http://localhost:3000"
echo "  Admin:    http://localhost:8000/admin/"
echo ""
echo "Run 'make logs' to view service logs."
