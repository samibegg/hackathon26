#!/usr/bin/env bash
# Copy canonical packages/migration-core into agent dirs that vendor it for Docker (/app mount).
# Demo monolith (rdbms-migration-poc-agent) uses inline src/.../migration/ — not synced here.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/packages/migration-core"

# Add agent folder names when you re-introduce production deployables, e.g.:
# AGENTS=(migration-intake-agent migration-build-agent)
AGENTS=()

if ((${#AGENTS[@]} == 0)); then
  echo "No agents configured. Canonical library: packages/migration-core"
  echo "See docs/PRODUCTION_MULTI_AGENT.md"
  exit 0
fi

for agent in "${AGENTS[@]}"; do
  dest="$ROOT/agents/$agent/migration-core"
  mkdir -p "$(dirname "$dest")"
  rsync -a --delete "$SRC/" "$dest/"
  echo "Synced migration-core -> agents/$agent/migration-core/"
done
