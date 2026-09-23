#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE=(docker compose -f docker-compose.postgres.yml)
echo "Starting demo PostgreSQL on localhost:5433 ..."
"${COMPOSE[@]}" up -d --wait

echo "Loading deterministic realistic synthetic data from demo/scenario.json ..."
python3 scripts/seed-postgres-scenario.py --reset "$@"

echo "Done. Use POSTGRES_URI=postgresql://commerce:commerce@localhost:5433/commerce_demo"
echo "From agentic dev (Docker): host.docker.internal instead of localhost."
