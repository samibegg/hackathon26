"""PostgreSQL connection helpers (local Docker Postgres or remote/Supabase)."""

from __future__ import annotations

import os
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import psycopg


def _is_local_dev_runtime() -> bool:
    """True when running inside agentengine local Docker, not cloud deploy."""
    # Platform local stack injects this hostname for Mongo; cloud does not.
    mongo = os.environ.get("MONGODB_URI", "")
    if re.match(r"^mongodb(\+srv)?://mongodb([:/?]|$)", mongo.strip()):
        return True
    return os.environ.get("AGENTENGINE_DEV", "").strip().lower() in {"1", "true", "yes"}


def resolve_postgres_uri(uri: str | None = None) -> str:
    """Return POSTGRES_URI, rewriting localhost only for local Docker runtimes."""
    value = (uri or os.environ.get("POSTGRES_URI", "")).strip()
    if not value:
        return ""
    if _is_local_dev_runtime():
        value = value.replace("@host:", "@host.docker.internal:")
        value = re.sub(r"@localhost:", "@host.docker.internal:", value)
        value = re.sub(r"@127\.0\.0\.1:", "@host.docker.internal:", value)
    return _ensure_ssl_for_remote(value)


def _ensure_ssl_for_remote(uri: str) -> str:
    """Add sslmode=require for remote hosts (Supabase/Atlas-style) when missing."""
    try:
        parts = urlsplit(uri)
    except ValueError:
        return uri
    host = (parts.hostname or "").lower()
    if not host or host in {"localhost", "127.0.0.1", "host.docker.internal", "postgres", "postgres-demo"}:
        return uri
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    if "sslmode" not in query:
        query["sslmode"] = "require"
    # Avoid libpq trying ~/.postgresql/postgresql.crt (unreadable in some sandboxes).
    query.setdefault("sslcert", "")
    query.setdefault("sslkey", "")
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )


def connect_postgres(uri: str | None = None, *, connect_timeout: int = 10):
    """Open a connection; avoid unreadable default ~/.postgresql client certs."""
    resolved = resolve_postgres_uri(uri)
    if not resolved:
        raise RuntimeError("POSTGRES_URI is not set")
    # Cloud tool sandboxes often ship a non-readable ~/.postgresql/postgresql.crt.
    # Point HOME at a clean temp dir so libpq does not open that path.
    prior = {k: os.environ.get(k) for k in ("HOME", "PGSSLCERT", "PGSSLKEY", "PGSSLROOTCERT")}
    tmp_home = os.environ.get("TMPDIR") or "/tmp"
    sandbox_home = os.path.join(tmp_home, "pg-home-empty")
    os.makedirs(sandbox_home, mode=0o755, exist_ok=True)
    os.environ["HOME"] = sandbox_home
    os.environ["PGSSLCERT"] = ""
    os.environ["PGSSLKEY"] = ""
    try:
        return psycopg.connect(resolved, connect_timeout=connect_timeout)
    finally:
        for key, value in prior.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def check_postgres() -> dict:
    """Verify Postgres is reachable and return table list + row counts for demo tables."""
    uri = resolve_postgres_uri()
    if not uri:
        return {"ok": False, "error": "POSTGRES_URI is not set"}
    demo_tables = ("customers", "products", "orders", "order_items", "payments")
    host = _host_from_uri(uri)
    try:
        with connect_postgres(uri, connect_timeout=10) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                counts: dict[str, int] = {}
                for table in demo_tables:
                    try:
                        cur.execute(f'SELECT COUNT(*) FROM "{table}"')  # noqa: S608
                        counts[table] = int(cur.fetchone()[0])
                    except psycopg.Error:
                        counts[table] = -1
        return {"ok": True, "uri_host": host, "row_counts": counts}
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "uri_host": host,
            "error": str(exc),
            "hint": (
                "Confirm project secret POSTGRES_URI reaches this runtime "
                "(Supabase: Session pooler URI with percent-encoded password and sslmode=require). "
                "Local Playground only: ./scripts/ensure-postgres-demo.sh and host.docker.internal:5433."
            ),
        }


def _host_from_uri(uri: str) -> str:
    match = re.search(r"@([^:/?]+)", uri)
    return match.group(1) if match else ""
