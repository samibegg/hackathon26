#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

./scripts/seed-postgres-demo.sh

docker exec \
  -e POSTGRES_URI='postgresql://commerce:commerce@postgres-demo:5432/commerce_demo' \
  rdbms-migration-poc-agent-app-1 \
  sh -lc 'set -a; . .agentic/tool-boot.env; set +a; PYTHONPATH=src python -m agent_rdbms_migration_poc.migration.e2e'
