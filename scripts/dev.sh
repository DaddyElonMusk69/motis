#!/usr/bin/env bash
# Start all Motis services for local development
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "🚀 Starting Motis dev stack..."

# Check for .env
if [ ! -f "$ROOT/.env" ]; then
  echo "⚠️  No .env found. Copying from .env.example..."
  cp "$ROOT/.env.example" "$ROOT/.env"
  echo "✏️  Edit $ROOT/.env with your API keys before continuing."
  exit 1
fi

# Start infra + all services via docker-compose
docker compose -f "$ROOT/infra/docker-compose.yml" up --build "$@"
