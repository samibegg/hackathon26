#!/usr/bin/env bash
# Full (re)seed of demo Postgres. Safe to re-run with --force; otherwise idempotent like ensure.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ "${1:-}" == "--force" ]]; then
  export DEMO_POSTGRES_FORCE_RESEED=1
fi
exec "$ROOT/scripts/ensure-postgres-demo.sh"
