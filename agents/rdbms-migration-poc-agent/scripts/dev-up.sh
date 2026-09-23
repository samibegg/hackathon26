#!/usr/bin/env bash
# Start demo Postgres (if needed) then the Agentic Playground stack.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

"$ROOT/scripts/ensure-postgres-demo.sh"

echo ""
echo "Starting agentic dev stack ..."
exec agentic dev up "$@"
