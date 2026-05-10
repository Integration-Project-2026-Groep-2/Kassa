#!/usr/bin/env bash
set -euo pipefail

echo "Running deploy script on $(hostname) as $(whoami)"
echo "PWD: $(pwd)"

# Use absolute paths to avoid issues with remote shells
PROJECT_DIR="$HOME/kassa"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.production.yml"

docker compose --project-directory "$PROJECT_DIR" -f "$COMPOSE_FILE" pull odoo
docker compose --project-directory "$PROJECT_DIR" -f "$COMPOSE_FILE" up -d
docker compose --project-directory "$PROJECT_DIR" -f "$COMPOSE_FILE" ps

echo "Deploy script finished"
