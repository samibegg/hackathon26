"""PostgreSQL connection helpers for local dev (Docker → host Postgres)."""

from __future__ import annotations

import os
import re

import psycopg


def resolve_postgres_uri(uri: str | None = None) -> str:
    """Normalize POSTGRES_URI for agentic dev containers reaching host Postgres."""
    value = (uri or os.environ.get("POSTGRES_URI", "")).strip()
    if not value:
        return ""
    # Common mistake: literal host "host" or localhost from inside Docker.
    value = value.replace("@host:", "@host.docker.internal:")
    value = re.sub(r"@localhost:", "@host.docker.internal:", value)
    value = re.sub(r"@127\.0\.0\.1:", "@host.docker.internal:", value)
    return value


def check_postgres() -> dict:
    """Verify Postgres is reachable and return table list + row counts for demo tables."""
    uri = resolve_postgres_uri()
    if not uri:
        return {"ok": False, "error": "POSTGRES_URI is not set"}
    demo_tables = ("customers", "products", "orders", "order_items", "payments")
    try:
        with psycopg.connect(uri, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                counts: dict[str, int] = {}
                for table in demo_tables:
                    try:
                        cur.execute(f'SELECT COUNT(*) FROM "{table}"')  # noqa: S608
                        counts[table] = int(cur.fetchone()[0])
                    except psycopg.Error:
                        counts[table] = -1
        return {"ok": True, "uri_host": _host_from_uri(uri), "row_counts": counts}
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": str(exc),
            "hint": "Run ./scripts/seed-postgres-demo.sh on the host and set POSTGRES_URI to "
            "postgresql://commerce:commerce@host.docker.internal:5433/commerce_demo",
        }


def _host_from_uri(uri: str) -> str:
    match = re.search(r"@([^:/]+)", uri)
    return match.group(1) if match else ""
