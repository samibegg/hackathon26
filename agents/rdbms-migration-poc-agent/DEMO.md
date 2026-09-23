# Migration PoC Generator — Demo Script (~10 minutes)

## Prerequisites

- `agentic dev up` for this agent
- `./scripts/seed-postgres-demo.sh` (Postgres on port **5433** — no local `psql` needed)
- `.env`: `OPENAI_API_KEY`, `POSTGRES_URI` (`host.docker.internal:5433` from Docker), and Mongo target — see **[`docs/DEMO_ENVIRONMENT.md`](../../docs/DEMO_ENVIRONMENT.md)** (local dev Mongo vs Atlas + `MIGRATION_TARGET_DB`)

## Test discovery transcript input (Playground)

1. Open `demo/playground-sample-payload.json` and copy the full JSON object.
2. In Playground, click **+** → **Add extra arguments**, paste the JSON, and **Attach**.
3. Send: `Score discovery completeness from my attached transcript.`
4. Confirm the agent reports completeness ≥ 0.8 for the Acme Retail sample.

(If your build shows a **Discovery call transcript** field, it is pre-filled from
`demo/discovery_transcript.md` via `agent.yaml` → `playground.inputs`.)

## Steps

| Step | Action | Audience sees |
|------|--------|----------------|
| 1 | Run seed script | 5 tables, ~25k rows |
| 2 | Playground: “Run the bundled e-commerce migration PoC” | Discovery + DDL loaded |
| 3 | Agent scores discovery, proposes schema | Completeness score, embed rationale |
| 4 | Approve HITL gates (discovery → schema → execution) | Review panels |
| 5 | Migration + validation tools run | Pass/fail reconciliation |
| 6 | Playground: “Show my PoC pack review” | Timestamped discovery-to-validation Markdown review |
| 7 | Atlas Data Explorer / Compass | `orders` with `line_items[]`, separate `payments` |

## Fallback (no LLM)

```bash
uv run migration-run --skip-llm
```

## One-command end-to-end smoke test

With `agentic dev up` running, execute:

```bash
./scripts/run-e2e-demo.sh
```

It reseeds Postgres, runs the deterministic Atlas migration, records a complete approved test pack,
and prints its persisted session ID plus Markdown review. It replaces the demo collections in
`MIGRATION_TARGET_DB`.

## Reusing a persisted PoC pack

PoC-pack reviews are scoped to the active Playground session. If a new session reports no
artifacts, ask the agent to list persisted PoC packs, then request a review using the returned
session ID. The stored pack remains immutable in the Atlas state database.

## Narrative

*“We had a discovery call Friday. By Monday we had a validated 5-table PoC in Atlas.”*

## Troubleshooting HITL resume

**“The agent could not be resumed”** — usually not a bad JSON payload. Check orchestration logs:

```bash
docker logs rdbms-migration-poc-agent-oe-1 2>&1 | tail -20
```

If you see `workflow is nondeterministic: step 2 committed with different state`, the suspended run cannot be replayed. **Start a new Playground session**, send one message such as *“Run the bundled e-commerce migration PoC end to end”*, and submit each HITL answer once (do not double-click Submit).

After changing `agent.yaml`, restart local dev: `agentic dev down && agentic dev up`.

**HITL answers:** plain language is enough (`Approved — proceed to schema design`). Include “reject” if you want to block the step.

## Troubleshooting data in Mongo / Compass

See **[`docs/DEMO_ENVIRONMENT.md`](../../docs/DEMO_ENVIRONMENT.md)** — wrong cluster, wrong database name (`MIGRATION_TARGET_DB` vs `commerce_poc`), local Mongo port, and Atlas network access.
