# Production architecture — multi-agent (reference)

This document describes the **recommended production deployment**: two physical agents with shared MongoDB workspace state. It is **not** what you run for the hackathon demo.

| Mode | Playgrounds | Repo path |
|------|-------------|-----------|
| **Demo** (default) | One | [`agents/rdbms-migration-poc-agent/`](../agents/rdbms-migration-poc-agent/) |
| **Production** (reference) | Two (or orchestrator + workers) | Implement from [`packages/migration-core/`](../packages/migration-core/) — no separate agent folders in this repo |

Demo script: [`agents/rdbms-migration-poc-agent/DEMO.md`](../agents/rdbms-migration-poc-agent/DEMO.md).

---

## Why split in production

- **Intake** and **build/migrate** often belong to different meetings, teams, or secret scopes.
- Smaller **tool surfaces** and `agent.yaml` sandboxes (Postgres-only vs Mongo migration keys).
- **Shared state** in `MIGRATION_STATE_MONGODB_URI` / `migration_poc_state.migration_workspace` avoids copying artifacts by hand.

Tradeoff: two Playgrounds (or explicit handoff UX) vs one continuous session — see [architecture.md](architecture.md#demo-vs-production).

---

## Agent 1 — `migration-intake-agent` (production)

**Job:** Discovery transcript, DDL, source inventory, Postgres checks, **HITL gate 1**, then handoff.

| Owns | Does not own |
|------|----------------|
| 10-area completeness scoring | Target schema approval (gate 2) |
| DDL parse + inventory + risk flags | `migration-plan.json` generation |
| Live Postgres connection / row counts | Migration execution or validation |
| **`approve_discovery_completeness`** | Gates 2–3 |

**Typical tools:** `load_bundled_demo_inputs`, `parse_postgres_ddl`, `build_source_inventory`, `score_discovery_completeness`, `check_postgres_connection`, `approve_discovery_completeness`, **`publish_engagement_handoff`**.

**State writes:** `discovery_transcript`, `discovery_score`, `source_inventory`, `ddl_text`, `hitl_discovery`, `handoff_status`, `engagement_id`.

---

## Agent 2 — `migration-build-agent` (production)

**Job:** Load intake from state, design, plan, **gates 2–3**, deterministic runner, validation.

| Owns | Does not own |
|------|----------------|
| Target schema + embed rationale | Re-litigating discovery (reads state) |
| `generate_migration_plan` | Gate 1 |
| **`approve_target_schema`**, **`approve_migration_execution`** | Raw transcript unless missing from state |
| `execute_migration_pipeline`, `run_validation_checks` | |

**Typical tools:** **`load_engagement_from_state`** (Playground extra args: `{ "engagement_id": "..." }`), `propose_target_schema_design`, `generate_migration_plan`, `check_mongodb_connection`, migrate + validate tools.

**State reads:** intake artifacts with `hitl_discovery.decision == approved`.  
**State writes:** `target_schema_design`, `migration_plan`, `hitl_schema`, `hitl_execution`, `migration_stats`, `validation_report`.

---

## Handoff contract

```mermaid
flowchart LR
  subgraph a1 [migration-intake-agent]
    T[transcript + DDL]
    I[inventory + score]
    H1[gate 1]
  end

  subgraph state [(migration_poc_state.migration_workspace)]
    DOC["_id = engagement_id"]
  end

  subgraph a2 [migration-build-agent]
    D[design + plan]
    H2[gate 2]
    H3[gate 3]
    RUN[runner]
  end

  T --> I --> H1 --> DOC
  DOC --> D --> H2 --> H3 --> RUN
```

1. Intake Playground → gate 1 → **`publish_engagement_handoff`** → note **`engagement_id`** (tool output or Compass).
2. Build Playground → extra arguments `{ "engagement_id": "<uuid>" }` → full build workflow.

Both agents use the same **`.env` pattern**:

- `MIGRATION_STATE_MONGODB_URI` + `MIGRATION_STATE_DB=migration_poc_state`
- `MONGODB_URI` + `MIGRATION_TARGET_DB=commerce_poc` (build agent / runner)
- `POSTGRES_URI`, LLM keys

If both stacks run on one laptop, offset **Playground ports** in each agent’s `dev.yaml` (default `3000` collides).

---

## Shared library

Canonical Python package for prod agents (runner, workspace with `engagement_id`, HITL formatters):

```text
packages/migration-core/
```

Docker **`agentic dev`** mounts only the agent directory as `/app`, so production deployables typically **vendor** `./migration-core` copied from `packages/migration-core` (see `scripts/sync-migration-core.sh` when you add prod agent folders again).

The **demo monolith** keeps migration code under `agents/rdbms-migration-poc-agent/src/agent_rdbms_migration_poc/` to avoid an extra vendored path for hackathon setup; keep behavior aligned with `packages/migration-core` when you change the runner or workspace.

---

## Alternative: one Playground orchestrator

For production UX without two Playgrounds, use a **single orchestrator agent** that calls intake/build **tools or subgraphs** (demo mode today) or invokes specialist agents via SDK with the same Mongo state — see [architecture.md](architecture.md).
