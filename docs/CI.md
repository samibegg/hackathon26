# Continuous Integration

## Pull-request CI

`.github/workflows/ci.yml` runs on pull requests and protected branches:

- Python 3.11 dependency sync
- unit tests
- Ruff
- whitespace validation
- a deterministic Postgres-to-local-Mongo migration and validation smoke test

It requires a repository secret named `MAGENTA_CLIENT_LIBRARIES_TOKEN`: a read-only GitHub
fine-grained token with access to `10gen/magenta-client-libraries`, used only to resolve the
private SDK dependencies.

## Atlas end-to-end

`.github/workflows/atlas-e2e.yml` is manual-only and runs in the protected `atlas-e2e`
environment. It writes only to `ci_migration_e2e`, seeds the demo source, runs the complete
deterministic migration, and stores its PoC pack under a `ci-<run-id>` session.

Configure these environment secrets:

- `MAGENTA_CLIENT_LIBRARIES_TOKEN`
- `MONGODB_URI`
- `MIGRATION_STATE_MONGODB_URI`

Never use a production migration database for `MIGRATION_TARGET_DB`; the workflow overrides it
with `ci_migration_e2e`.
