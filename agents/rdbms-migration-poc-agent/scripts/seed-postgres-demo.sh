#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE=(docker compose -f docker-compose.postgres.yml)
PSQL=( "${COMPOSE[@]}" exec -T postgres-demo psql -v ON_ERROR_STOP=1 -U commerce -d commerce_demo )

echo "Starting demo PostgreSQL on localhost:5433 ..."
"${COMPOSE[@]}" up -d --wait

echo "Applying schema ..."
"${PSQL[@]}" < demo/schema.sql

echo "Loading seed data (this may take a minute) ..."
"${PSQL[@]}" < demo/seed.sql

echo "Row counts:"
"${PSQL[@]}" -c "
SELECT 'customers' AS rel, COUNT(*) FROM customers
UNION ALL SELECT 'products', COUNT(*) FROM products
UNION ALL SELECT 'orders', COUNT(*) FROM orders
UNION ALL SELECT 'order_items', COUNT(*) FROM order_items
UNION ALL SELECT 'payments', COUNT(*) FROM payments;
"

echo "Done. Use POSTGRES_URI=postgresql://commerce:commerce@localhost:5433/commerce_demo"
echo "From agentic dev (Docker): host.docker.internal instead of localhost."
