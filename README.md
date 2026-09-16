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
| Discovery 10-area keyword scorer | Done | Gate at 0.8 in scorer; not fully enforced in tools |
| DDL parser + source inventory | Done | Lightweight parser; FK references |
| Canonical target schema + embed rationale | Done | Bundled e-commerce + `simple_three_table` workshop |
| LangGraph orchestrator + tools | Done | Six “specialist” roles via tools (single runtime) |
| HITL interrupts (3 gates) | Partial | Execution gate enforced in code; discovery/schema rely on prompt |
| Playground transcript input | Partial | `agent.yaml` input + `playground-sample-payload.json` |
| Playground artifact panels | Not started | Session JSON via `get_session_artifacts` only |
| Structured LLM discovery intake | Not started | Keyword score only |
| Plan synthesis from inventory | Partial | Demo loads **reference plan** when 5 tables match |
| CI / golden migration tests | Not started | Unit tests in agent; no GitHub Actions |
| Skills + procedural memory | Not started | Spec Phase 4 |

**Architecture (MVP):** one **Migration Orchestrator** (LLM + LangGraph) delegates to **deterministic tools** named for Discovery Extractor, Source Modeler, Target Designer, Pipeline Architect, PoC Builder, and Validation — not separate agent runtimes yet.

---

## Layout

- `project-config.yaml` — project-level memory settings (platform)
- `agents/rdbms-migration-poc-agent/` — runnable agent (`agentic dev up` from that directory)

Agent docs: [`agents/rdbms-migration-poc-agent/README.md`](agents/rdbms-migration-poc-agent/README.md) (quick start), [`DEMO.md`](agents/rdbms-migration-poc-agent/DEMO.md) (~10 min live demo).

---

## Quick start

```bash
cd agents/rdbms-migration-poc-agent
cp env.example .env   # OPENAI_API_KEY, POSTGRES_URI, MONGODB_URI

./scripts/seed-postgres-demo.sh   # optional: Postgres on localhost:5433
agentic dev up                    # Playground http://localhost:3000
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
| **1** | Postgres bundle + deterministic runner | **Largely complete** |
| **2** | Discovery + design in Playground (artifacts, intake, plan builder) | **In progress** |
| **3** | HITL enforcement + full Playground demo hardening | **Partial** |
| **4** | Skills, procedural memory, CI, docs, upstream to `magenta-examples` | **Not started** |

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

- [ ] **GitHub Actions:** `uv sync`, unit tests; optional Postgres service job.
- [ ] **Integration/golden tests:** validation fixtures; headless migration smoke (with secrets in CI or skipped).
- [ ] **Skills** extracted per spec (Postgres inventory, MongoDB schema design, migration validation).
- [ ] **Procedural memory** / playbook replay (optional; align with platform memory when needed).
- [ ] **Upstream PR** to `magenta-examples` with demo script and operator runbook.

### Decisions (track here)

- [ ] Confirm **final repo home** (hackathon26 only vs PR to `magenta-examples`).
- [ ] Confirm **multi-agent UI** requirement (separate subagents vs orchestrator + tools).
- [ ] Confirm **discovery depth** for MVP (keyword gate + template intake vs LLM extraction to JSON).
- [ ] Confirm **demo target Mongo** (local `agentic dev` vs Atlas-only).

---

## MVP success criteria

A Technical Architect can:

1. Run `scripts/seed-postgres-demo.sh` and `agentic dev up`
2. Paste the bundled discovery transcript and load DDL in Playground
3. Review and approve target schema at HITL gates
4. Execute migration and see all five source tables represented in MongoDB (four collections + embedded line items)
5. Review a validation report (row counts + embedded integrity)
6. Complete the full demo in under 10 minutes (with headless fallback if LLM fails)

---

## Prerequisites

- LLM API key (`OPENAI_API_KEY`; Grove `OPENAI_BASE_URL` optional)
- MongoDB target (`MONGODB_URI` — local dev from `agentic dev` or Atlas `commerce_poc`)
- Docker (demo Postgres)
- [`uv`](https://docs.astral.sh/uv/) for Python deps and tests
