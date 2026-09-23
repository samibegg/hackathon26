# Migration PoC Generator (hackathon26)

**RDBMS-to-MongoDB migration PoC generator** for MongoDB Technical Architects — built on the MongoDB Agentic Platform (LangGraph + `magenta-sdklanggraph`).

Turn a **discovery call transcript** and **PostgreSQL DDL** into a **PoC pack**: structured intake, source inventory, target schema design, field mapping, migration plan, **deterministic load into Atlas**, and a **validation report**. Human-in-the-loop gates keep architect judgment on discovery, schema, and execution.

Long-term target: contribute a polished agent to [`magenta-examples`](https://github.com/10gen/magenta-examples). This repo is the active MVP workspace.

---

## Vision (MVP)

| Input | Output (PoC pack) |
|-------|-------------------|
| Discovery transcript (10-area playbook) | Structured discovery summary + completeness score |
| PostgreSQL DDL (5-table subset) | Source inventory, relationship hints, risk flags |
| Optional live Postgres (`POSTGRES_URI`) | Row counts + migration source |
| Architect approvals (3 gates) | Runnable migration + validation in target DB (e.g. `commerce_poc`) |

**Demo scenario:** e-commerce order management — `customers`, `products`, `orders`, `order_items`, `payments` → four MongoDB collections with **`line_items[]` embedded under `orders`** and **`payments` separate** (audit/compliance).

**Design principle:** agents **reason and propose**; a **deterministic runner** executes from `migration-plan.json` so demos and production PoCs stay trustworthy.

---

## Current state

What works today in `agents/rdbms-migration-poc-agent/`:

| Area | Status | Notes |
|------|--------|--------|
| Demo Postgres + seed (~25k rows) | Done | `docker-compose.postgres.yml`, `scripts/seed-postgres-demo.sh` |
| Deterministic Postgres → Mongo runner | Done | Embed logic, indexes, `migration-run --skip-llm` |
| Reference `migration-plan.json` | Done | `demo/migration-plan.reference.json` |
| Discovery 10-area keyword scorer | Done | `ready_for_poc` at 0.8 in scorer; not enforced in plan/migrate tools |
| DDL parser + source inventory | Done | Lightweight parser; FK references; optional live row counts |
| Canonical target schema + embed rationale | Done | Bundled e-commerce + `simple_three_table` workshop |
| LangGraph orchestrator + tools | Done | Six “specialist” roles via tools (single runtime) |
| Session workspace (file or MongoDB) | Done | `MIGRATION_STATE_MONGODB_URI` + file fallback; see `workspace.py` |
| Postgres pre-flight | Done | `check_postgres_connection` |
| HITL interrupts (3 gates) | Partial | Gate 3 enforced before `execute_migration_pipeline`; gates 1–2 interrupt + artifacts but not checked on downstream tools |
| HITL Playground UX | Done | Markdown review briefs; plain-language approve/reject |
| Playground transcript input | Done | `agent.yaml` transcript field + `playground-sample-payload.json` extra args |
| Playground artifact panels | Not started | Session JSON via `get_session_artifacts` only |
| Operator / architecture docs | Done | `docs/DEMO_ENVIRONMENT.md`, `architecture.md`, demo script |
| Structured LLM discovery intake | Not started | Keyword score only |
| Plan synthesis from inventory | Partial | Loads **reference plan** when 5-table inventory matches; not derived from approved design |
| CI / golden migration tests | Not started | Unit tests in agent; no GitHub Actions |
| Skills + procedural memory | Not started | Spec Phase 4 |

**Architecture (demo):** one **Migration Orchestrator** (LLM + LangGraph) delegates to **deterministic tools** named for six specialist roles — not separate deployable agents. Production may split intake vs build; see [`docs/PRODUCTION_MULTI_AGENT.md`](docs/PRODUCTION_MULTI_AGENT.md).

---

## Demo vs production

| | Demo (run this) | Production (documented only) |
|--|-----------------|------------------------------|
| Agent folder | `agents/rdbms-migration-poc-agent/` | `migration-intake-agent` + `migration-build-agent` |
| Playgrounds | One (`agentic dev up`) | Two or orchestrator + workers |
| Docs | [`DEMO.md`](agents/rdbms-migration-poc-agent/DEMO.md), [`architecture.md`](docs/architecture.md) | [`PRODUCTION_MULTI_AGENT.md`](docs/PRODUCTION_MULTI_AGENT.md) |

---

## Layout

- `project-config.yaml` — project-level memory settings (platform)
- [`docs/DEMO_ENVIRONMENT.md`](docs/DEMO_ENVIRONMENT.md) — Postgres seed, Atlas vs local Mongo, Compass
- [`docs/architecture.md`](docs/architecture.md) — demo orchestrator, MongoDB state, env vars
- [`docs/PRODUCTION_MULTI_AGENT.md`](docs/PRODUCTION_MULTI_AGENT.md) — two-agent production reference
- `packages/migration-core/` — shared runner, workspace, HITL (for prod agents; demo uses inline code)
- `agents/rdbms-migration-poc-agent/` — **demo agent** (`agentic dev up`)

Agent docs: [`agents/rdbms-migration-poc-agent/README.md`](agents/rdbms-migration-poc-agent/README.md), [`DEMO.md`](agents/rdbms-migration-poc-agent/DEMO.md).

---

## Quick start

```bash
cd agents/rdbms-migration-poc-agent
cp env.example .env   # includes COMPOSE_FILE to start Postgres with agentic dev up

agentic dev up        # Playground :3000 + demo Postgres :5433
```

Headless fallback (no LLM):

```bash
cd agents/rdbms-migration-poc-agent
export POSTGRES_URI=postgresql://commerce:commerce@localhost:5433/commerce_demo
export MONGODB_URI=...
uv run migration-run --skip-llm
```

---

## Implementation plan (phases)

Aligned with the MVP proposal (~2 weeks to demo-ready):

| Phase | Focus | Repo status |
|-------|--------|-------------|
| **1** | Postgres bundle + deterministic runner | **Complete** (bundled e-commerce demo) |
| **2** | Discovery + design in Playground (artifacts, intake, plan builder) | **In progress** |
| **3** | HITL enforcement + full Playground demo hardening | **Partial** (execution gate in code; gates 1–2 prompt + interrupts) |
| **4** | Skills, procedural memory, CI, upstream to `magenta-examples` | **Partial** — operator/architecture docs done; CI, skills, upstream not started |

---

## TODOs (backlog)

Prioritized next work — no code committed for these until picked up:

### P0 — Demo trust and success criteria

- [ ] **Enforce HITL gates in tools:** require approved discovery + schema before `execute_migration_pipeline` (execution already checked).
- [ ] **Enforce completeness gate:** block plan generation / migration when score &lt; 0.8 unless gate 1 records an explicit waiver.
- [ ] **Deterministic plan generation:** build `migration-plan.json` from inventory + approved design; golden test equals `demo/migration-plan.reference.json` for bundled DDL.
- [ ] **Mongo pre-flight:** `check_mongodb_connection` (symmetric with Postgres).

### P1 — PoC pack visibility

- [ ] **Playground artifacts** for discovery summary, target schema, field mapping, validation report (follow `data-analyst-agent` / platform patterns in `magenta-examples`).
- [ ] **Standalone discovery playbook** (`docs/discovery-playbook.md`) for field review — 10 sections, required fields, assumptions.
- [ ] **Transcript ↔ DDL cross-check** in source inventory (table names, risk flags).
- [ ] **Pipeline architecture** artifact (extract → transform → load → validate; cutover out of scope).

### P2 — Quality and reuse

- [ ] **LangGraph subgraphs or tool groups** for clearer specialist phases without second Playground (optional UX polish on demo agent).
- [ ] **GitHub Actions:** `uv sync`, unit tests; optional Postgres service job.
- [ ] **Integration/golden tests:** validation fixtures; headless migration smoke (with secrets in CI or skipped).
- [ ] **Skills** extracted per spec (Postgres inventory, MongoDB schema design, migration validation).
- [ ] **Procedural memory** / playbook replay (optional; align with platform memory when needed).
- [ ] **Upstream PR** to `magenta-examples` with demo script and operator runbook.

### Decisions (track here)

- [ ] Confirm **final repo home** (hackathon26 only vs PR to `magenta-examples`).
- [x] **Multi-agent UI:** demo stays **one Playground** (orchestrator + tools); production split documented in [`docs/PRODUCTION_MULTI_AGENT.md`](docs/PRODUCTION_MULTI_AGENT.md).
- [ ] Confirm **discovery depth** for MVP (keyword gate + template intake vs LLM extraction to JSON).
- [x] **Demo target Mongo:** local dev stack Mongo **or** Atlas via `.env` (`MIGRATION_TARGET_DB`, e.g. `commercedb`) — [`docs/DEMO_ENVIRONMENT.md`](docs/DEMO_ENVIRONMENT.md).

---

## MVP success criteria

A Technical Architect can:

1. Run `./scripts/dev-up.sh` or `agentic dev up` with `COMPOSE_FILE` in `.env` (see `env.example`)
2. Use the bundled discovery transcript (Playground input or extra args) and load DDL in Playground
3. Review and approve target schema at HITL gates
4. Execute migration and see all five source tables represented in MongoDB (four collections + embedded line items)
5. Review a validation report (row counts + embedded integrity)
6. Complete the full demo in under 10 minutes (with headless fallback if LLM fails)

---

## Prerequisites

- LLM API key (`OPENAI_API_KEY`; Grove `OPENAI_BASE_URL` optional)
- MongoDB target — unset `MONGODB_URI` for local dev stack Mongo, or Atlas + `MIGRATION_TARGET_DB` (see [`docs/DEMO_ENVIRONMENT.md`](docs/DEMO_ENVIRONMENT.md))
- Docker (demo Postgres)
- [`uv`](https://docs.astral.sh/uv/) for Python deps and tests
