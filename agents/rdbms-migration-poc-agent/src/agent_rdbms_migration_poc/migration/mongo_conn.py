"""MongoDB target connection checks for migration execution."""

from __future__ import annotations

import os
from typing import Any

from pymongo import MongoClient


def resolve_target_database(plan: dict[str, Any] | None = None) -> str:
    """Resolve the target database consistently for pre-flight and execution."""
    return os.environ.get("MIGRATION_TARGET_DB", "").strip() or (plan or {}).get("target", {}).get(
        "database", "commerce_poc"
    )


def check_mongodb(plan: dict[str, Any] | None = None) -> dict[str, Any]:
    """Verify MONGODB_URI is reachable and the configured target database is accessible."""
    uri = os.environ.get("MONGODB_URI", "").strip()
    if not uri:
        return {"ok": False, "error": "MONGODB_URI is not set"}
    target_database = resolve_target_database(plan)
    try:
        with MongoClient(uri, serverSelectionTimeoutMS=5_000) as client:
            client.admin.command("ping")
            client[target_database].command("ping")
        return {"ok": True, "target_database": target_database}
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": str(exc),
            "hint": "Check MONGODB_URI, Atlas network access, and write permissions for MIGRATION_TARGET_DB.",
        }
