# Demo environment — Postgres, MongoDB, Compass

Operator guide for **`agents/rdbms-migration-poc-agent/`** local demos. Live script: [`DEMO.md`](../agents/rdbms-migration-poc-agent/DEMO.md).

---

## Overview

| System | Role | Typical setup |
|--------|------|----------------|
| **PostgreSQL** | Migration **source** (demo data) | Docker on host port **5433** via seed script |
| **`MONGODB_URI`** | Migration **target** (loaded PoC data) | Local `agentic dev` Mongo **or** **MongoDB Atlas** |
| **`MIGRATION_STATE_MONGODB_URI`** (optional) | Session artifacts (plan, HITL) | Same or different cluster; DB `migration_poc_state` |

The deterministic runner writes **customer-shaped data** only to **`MONGODB_URI`** + database **`MIGRATION_TARGET_DB`**. It does not load orders into the state DB.

---

## PostgreSQL (required for full migrate + validate)

### Start Postgres with `agentic dev up` (recommended)

1. `cp env.example .env` and set secrets (`OPENAI_API_KEY`, Mongo targets, etc.).
2. Ensure `.env` includes **`COMPOSE_FILE`** (in `env.example`) so the dev stack merges `docker-compose.postgres.yml`.
3. Run:

```bash
agentic dev up
```

Playground on **http://localhost:3000**; Postgres on **5433**. On a **new** Docker volume, Postgres runs `demo/schema.sql` and `demo/seed.sql` once via `docker-entrypoint-initdb.d` (first start can take ~1 minute).

If you already had a Postgres volume from an older setup, run `./scripts/seed-postgres-demo.sh --force` or remove the `postgres-demo-data` volume and restart dev.

### Postgres only (troubleshooting)

```bash
./scripts/ensure-postgres-demo.sh
```

Full reset of demo data:

```bash
./scripts/seed-postgres-demo.sh --force
```

`./scripts/dev-up.sh` is equivalent to `ensure-postgres-demo.sh` + `agentic dev up` when you are **not** using `COMPOSE_FILE` in `.env`.

### `POSTGRES_URI` by runtime

| Where code runs | `POSTGRES_URI` host |
|-----------------|---------------------|
| **`agentic dev`** (agent/tool in Docker) | `host.docker.internal:5433` |
| **Host CLI** (`uv run migration-run`) | `localhost:5433` |

Example (Playground / dev):

```bash
POSTGRES_URI=postgresql://commerce:commerce@host.docker.internal:5433/commerce_demo
```

---

## MongoDB target — local dev vs Atlas

### Option A — Local Mongo from `agentic dev` (default)

If **`MONGODB_URI`** is unset in `.env`, the platform usually injects the dev stack Mongo (Docker). Migrated data appears on a **random localhost port**, not `27017`.

Find the port:

```bash
docker port rdbms-migration-poc-agent-mongodb-1 27017
# e.g. 127.0.0.1:64510
```

**Compass:** `mongodb://127.0.0.1:<port>` → database **`commerce_poc`** (or your `MIGRATION_TARGET_DB`).

Port changes when you `agentic dev down && agentic dev up`.

### Option B — MongoDB Atlas via Playground (field demo)

Set in **`agents/rdbms-migration-poc-agent/.env`**:

```bash
MONGODB_URI=mongodb+srv://USER:PASS@cluster.mongodb.net/
MIGRATION_TARGET_DB=commerce_poc   # or commercedb — must match Atlas DB name you open
```

- **`agentengine` injects local Mongo** for the platform checkpointer and protects process `MONGODB_URI`. The **migration runner** still reads Atlas from this **`.env` file** when `MONGODB_URI` is `mongodb+srv` / `*.mongodb.net` (or set `MIGRATION_TARGET_MONGODB_URI` explicitly).
- **`MIGRATION_TARGET_DB`** is the database name for loaded PoC data.
- **Atlas Network Access** must allow the **tool container** egress (often `0.0.0.0/0` for hackathons).
- Database user needs **readWrite** on the target database.

After changing `.env`, restart if needed, then in Playground call **`check_mongodb_connection`** — expect `"uri_kind": "atlas"`. Re-run gate 3 + migrate; prior local-docker loads do **not** copy to Atlas.

**Compass / Data Explorer:** same Atlas cluster as `.env`, database **`MIGRATION_TARGET_DB`**, collections `customers`, `products`, `orders`, `payments`.

### Optional — state DB on Atlas

Session artifacts (plan, HITL, validation JSON in workspace):

```bash
MIGRATION_STATE_MONGODB_URI=mongodb+srv://USER:PASS@cluster.mongodb.net/
MIGRATION_STATE_DB=migration_poc_state
```

Leave **`MIGRATION_STATE_MONGODB_URI`** empty for file-backed workspace under `.agentic/migration-sessions/`.

---

## “I ran the pipeline but don’t see data in Mongo”

1. **Wrong cluster** — Compass on Atlas while migration used local dev Mongo (empty `MONGODB_URI` in `.env`).
2. **Wrong database name** — looking at `commerce_poc` while `MIGRATION_TARGET_DB=commercedb`.
3. **Wrong DB role** — browsing `migration_poc_state` (artifacts only, not loaded commerce collections).
4. **Local dev** — Compass on `27017` instead of the port from `docker port … mongodb-1 27017`.
5. **Migration didn’t run** — check Playground tool result for `execute_migration_pipeline` errors, or ask the agent for `get_session_artifacts` (`migration_stats`, `validation_report`).

Verify from terminal (local dev Mongo):

```bash
docker exec rdbms-migration-poc-agent-mongodb-1 mongosh commerce_poc --quiet --eval \
  'db.getCollectionNames().forEach(c => print(c+": "+db[c].countDocuments()))'
```

(Use your `MIGRATION_TARGET_DB` name instead of `commerce_poc` if different.)

---

## Headless migration on the host

```bash
cd agents/rdbms-migration-poc-agent
export POSTGRES_URI=postgresql://commerce:commerce@localhost:5433/commerce_demo
export MONGODB_URI='mongodb+srv://...'   # or local URI with published port
export MIGRATION_TARGET_DB=commercedb
uv run migration-run --skip-llm
```

More detail on env vars: [`architecture.md`](architecture.md).
