#!/usr/bin/env bash
# Load demo schema + seed into a Supabase (or any) Postgres using Dockerized psql.
# Usage:
#   export POSTGRES_URI='postgresql://postgres.xxx:PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres'
#   ./scripts/seed-supabase.sh
#
# Prefer the Session pooler URI (port 5432) from Dashboard → Connect.
# Add ?sslmode=require if the provider requires it (Supabase usually does).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
URI="${POSTGRES_URI:-${DATABASE_URL:-}}"

if [[ -z "$URI" ]]; then
  echo "Set POSTGRES_URI to your Supabase connection string (Session pooler recommended)." >&2
  exit 1
fi

# Ensure sslmode for Supabase if missing
if [[ "$URI" != *"sslmode="* ]]; then
  if [[ "$URI" == *"?"* ]]; then
    URI="${URI}&sslmode=require"
  else
    URI="${URI}?sslmode=require"
  fi
fi

echo "Applying demo/schema.sql ..."
docker run --rm -i \
  -v "$ROOT/demo:/demo:ro" \
  postgres:16-alpine \
  psql -v ON_ERROR_STOP=1 "$URI" -f /demo/schema.sql

echo "Applying demo/seed.sql (~25k rows) ..."
docker run --rm -i \
  -v "$ROOT/demo:/demo:ro" \
  postgres:16-alpine \
  psql -v ON_ERROR_STOP=1 "$URI" -f /demo/seed.sql

echo "Row counts:"
docker run --rm -i \
  postgres:16-alpine \
  psql -v ON_ERROR_STOP=1 "$URI" -c "
SELECT 'customers' AS rel, COUNT(*) FROM customers
UNION ALL SELECT 'products', COUNT(*) FROM products
UNION ALL SELECT 'orders', COUNT(*) FROM orders
UNION ALL SELECT 'order_items', COUNT(*) FROM order_items
UNION ALL SELECT 'payments', COUNT(*) FROM payments;
"

echo ""
echo "Done. Set this as the Agent Engine project secret POSTGRES_URI (same URI),"
echo "then: agentengine secret sync  # or agentengine deploy"
