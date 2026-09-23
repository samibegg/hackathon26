# rdbms-migration-poc-agent (demo)

**Single Playground** migration PoC generator for hackathon demos and local MVP work.

One **Migration Orchestrator** LangGraph app performs six logical specialist roles via **tools** (discovery, inventory, design, plan, HITL gates, deterministic migrate + validate). See [`../../docs/architecture.md`](../../docs/architecture.md).

Production deployments may split **intake** vs **build** into separate agents — that layout is documented only, not shipped in this repo: [`../../docs/PRODUCTION_MULTI_AGENT.md`](../../docs/PRODUCTION_MULTI_AGENT.md).

Shared runner/workspace reference library (for future prod agents): [`../../packages/migration-core/`](../../packages/migration-core/).

## Quick start

```bash
cp env.example .env               # COMPOSE_FILE merges Postgres into agentic dev up
agentic dev up                    # Playground http://localhost:3000 + Postgres :5433
```

Fallback: `./scripts/dev-up.sh` or `./scripts/ensure-postgres-demo.sh` if Postgres is not in the stack.

Live demo script: [`DEMO.md`](DEMO.md).

Headless:

```bash
export POSTGRES_URI=postgresql://commerce:commerce@localhost:5433/commerce_demo
export MONGODB_URI=...
uv run migration-run --skip-llm
```
