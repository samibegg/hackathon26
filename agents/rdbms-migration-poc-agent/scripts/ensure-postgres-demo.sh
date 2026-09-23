#!/usr/bin/env bash
# Start demo Postgres on :5433 and seed once (idempotent). Used by dev-up.sh and seed script.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE=(docker compose -p rdbms-migration-poc-postgres -f docker-compose.postgres.yml)
PSQL=( "${COMPOSE[@]}" exec -T postgres-demo psql -v ON_ERROR_STOP=1 -U commerce -d commerce_demo )

echo "Starting demo PostgreSQL on localhost:5433 ..."
"${COMPOSE[@]}" up -d --wait

_is_seeded() {
  local count
  count=$("${PSQL[@]}" -t -A -c "SELECT COUNT(*) FROM customers;" 2>/dev/null || echo "0")
  [[ "${count:-0}" =~ ^[0-9]+$ ]] && (( count >= 2000 ))
}

_print_row_counts() {
  echo "Row counts:"
  "${PSQL[@]}" -c "
SELECT 'customers' AS rel, COUNT(*) FROM customers
UNION ALL SELECT 'products', COUNT(*) FROM products
UNION ALL SELECT 'orders', COUNT(*) FROM orders
UNION ALL SELECT 'order_items', COUNT(*) FROM order_items
UNION ALL SELECT 'payments', COUNT(*) FROM payments;
"
}

if [[ "${DEMO_POSTGRES_FORCE_RESEED:-}" == "1" ]]; then
  echo "Force reseed: resetting public schema ..."
  "${PSQL[@]}" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO commerce; GRANT ALL ON SCHEMA public TO public;"
elif _is_seeded; then
  echo "Demo PostgreSQL already seeded."
  _print_row_counts
  echo "POSTGRES_URI (agentengine dev): postgresql://commerce:commerce@host.docker.internal:5433/commerce_demo"
  exit 0
fi

echo "Applying schema ..."
"${PSQL[@]}" < demo/schema.sql

echo "Loading seed data (this may take a minute) ..."
"${PSQL[@]}" < demo/seed.sql

_print_row_counts
echo "POSTGRES_URI (agentengine dev): postgresql://commerce:commerce@host.docker.internal:5433/commerce_demo"
