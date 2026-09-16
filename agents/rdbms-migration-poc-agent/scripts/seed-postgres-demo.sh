#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "Starting demo PostgreSQL on localhost:5433 ..."
docker compose -f docker-compose.postgres.yml up -d --wait

export PGHOST=localhost
export PGPORT=5433
export PGUSER=commerce
export PGPASSWORD=commerce
export PGDATABASE=commerce_demo

echo "Applying schema ..."
psql -v ON_ERROR_STOP=1 -f demo/schema.sql

echo "Loading seed data (this may take a minute) ..."
psql -v ON_ERROR_STOP=1 -f demo/seed.sql

echo "Row counts:"
psql -c "
SELECT 'customers' AS rel, COUNT(*) FROM customers
UNION ALL SELECT 'products', COUNT(*) FROM products
UNION ALL SELECT 'orders', COUNT(*) FROM orders
UNION ALL SELECT 'order_items', COUNT(*) FROM order_items
UNION ALL SELECT 'payments', COUNT(*) FROM payments;
"

echo "Done. Use POSTGRES_URI=postgresql://commerce:commerce@localhost:5433/commerce_demo"
