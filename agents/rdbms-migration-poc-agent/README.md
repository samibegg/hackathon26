# rdbms-migration-poc-agent (demo)

**Single Playground** migration PoC generator for hackathon demos and local MVP work.

One **Migration Orchestrator** LangGraph app performs six logical specialist roles via **tools** (discovery, inventory, design, plan, HITL gates, deterministic migrate + validate). See [`../../docs/architecture.md`](../../docs/architecture.md).

Production deployments may split **intake** vs **build** into separate agents — that layout is documented only, not shipped in this repo: [`../../docs/PRODUCTION_MULTI_AGENT.md`](../../docs/PRODUCTION_MULTI_AGENT.md).

Shared runner/workspace reference library (for future prod agents): [`../../packages/migration-core/`](../../packages/migration-core/).

## Quick start

```bash
cp env.example .env               # Atlas or local Mongo — see ../../docs/DEMO_ENVIRONMENT.md
./scripts/seed-postgres-demo.sh   # required for full migrate (Postgres :5433)
agentic dev up                    # Playground http://localhost:3000
```

Live demo script: [`DEMO.md`](DEMO.md).

Headless:

```bash
export POSTGRES_URI=postgresql://commerce:commerce@localhost:5433/commerce_demo
export MONGODB_URI=...
uv run migration-run --skip-llm
```
