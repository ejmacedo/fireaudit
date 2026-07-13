#!/bin/sh
# Production deploy script — runs on VPS via CI SSH step.
# Assumes /opt/fireaudit contains docker-compose.yml and .env.

set -e

cd /opt/fireaudit

echo "Pulling latest images..."
docker compose pull

echo "Starting services..."
docker compose up -d --remove-orphans

echo "Running database migrations..."
docker compose exec -T api alembic upgrade head

echo "Cleaning up old images..."
docker system prune -f

echo "Deploy complete."
