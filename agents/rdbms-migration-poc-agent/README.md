# rdbms-migration-poc-agent

Migration PoC Generator — turns a **discovery transcript** and **PostgreSQL DDL** into a **deterministic migration** and **validation report** for MongoDB Atlas.

Project **vision, current state, phased plan, and TODO backlog** live in the [repo root README](../../README.md).

## Quick start

```bash
cp env.example .env
# Set OPENAI_API_KEY (+ OPENAI_BASE_URL if using Grove)

./scripts/seed-postgres-demo.sh   # optional: local Postgres on :5433

agentic dev up
```

Playground: http://localhost:3000 — ask to run the bundled e-commerce migration PoC workflow.

## Headless migration (no LLM)

```bash
export POSTGRES_URI=postgresql://commerce:commerce@localhost:5433/commerce_demo
export MONGODB_URI=...   # from agentic dev or Atlas
uv run migration-run --skip-llm --plan demo/migration-plan.reference.json
```

## DDL examples

| ID | Tables | Migration runner |
|----|--------|------------------|
| `simple_three_table` | customers, orders, order_lines | Design / parse only |
| `ecommerce_mvp` | 5-table commerce demo | Full pipeline |

In Playground: *“Load the simple three table DDL example and parse it.”*

## Layout

- `demo/examples/simple_three_table/` — minimal PostgreSQL DDL sample
- `demo/` — full transcript, DDL, seed SQL, reference `migration-plan.json`
- `demo/playground-sample-payload.json` — copy into Playground **Extra arguments** to test transcript input
- `src/agent_rdbms_migration_poc/migration/` — deterministic runner
- `docker-compose.postgres.yml` — demo source database

See [DEMO.md](./DEMO.md) for the live presentation script.
