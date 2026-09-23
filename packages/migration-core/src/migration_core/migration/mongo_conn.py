"""Resolve MongoDB URI for PoC migration data (Playground vs Atlas).

``agentengine dev up`` injects ``MONGODB_URI=mongodb://mongodb:27017`` for the
platform checkpointer and treats that key as protected, so Atlas URIs in
``.env`` never replace the process env. Migration/validation must still honor
the agent's ``.env`` when it points at Atlas.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from migration_core.paths import agent_root


def _is_platform_local_mongo(uri: str) -> bool:
    """True for the compose service hostname used by agentengine local Mongo."""
    return bool(re.match(r"^mongodb(\+srv)?://mongodb([:/?]|$)", uri.strip()))


def _looks_like_atlas(uri: str) -> bool:
    u = uri.strip().lower()
    return u.startswith("mongodb+srv://") or "mongodb.net" in u


def _read_dotenv_value(key: str) -> str:
    candidates = (
        agent_root() / ".env",
        Path("/app/.env"),
        Path.cwd() / ".env",
    )
    seen: set[Path] = set()
    for path in candidates:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved in seen or not resolved.is_file():
            continue
        seen.add(resolved)
        try:
            lines = resolved.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            if name.strip() != key:
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                value = value[1:-1]
            return value.strip()
    return ""


def resolve_migration_mongodb_uri() -> str:
    """URI used by the deterministic runner (PoC customer data), not platform state."""
    explicit = os.environ.get("MIGRATION_TARGET_MONGODB_URI", "").strip()
    if explicit:
        return explicit

    process_uri = os.environ.get("MONGODB_URI", "").strip()
    file_uri = _read_dotenv_value("MONGODB_URI")

    # Prefer Atlas from .env when the runtime was forced onto local Docker Mongo.
    if file_uri and _looks_like_atlas(file_uri) and (
        not process_uri or _is_platform_local_mongo(process_uri)
    ):
        return file_uri

    return process_uri or file_uri


def resolve_migration_target_db(plan_default: str = "commerce_poc") -> str:
    env_db = os.environ.get("MIGRATION_TARGET_DB", "").strip()
    if env_db:
        return env_db
    file_db = _read_dotenv_value("MIGRATION_TARGET_DB")
    return file_db or plan_default


def mongodb_uri_kind(uri: str) -> str:
    if not uri:
        return "empty"
    if _looks_like_atlas(uri):
        return "atlas"
    if _is_platform_local_mongo(uri):
        return "local-docker"
    return "other"


def check_mongodb() -> dict:
    """Pre-flight for the migration target (Atlas or local)."""
    uri = resolve_migration_mongodb_uri()
    db_name = resolve_migration_target_db()
    if not uri:
        return {
            "ok": False,
            "error": "No migration MongoDB URI (set MONGODB_URI or MIGRATION_TARGET_MONGODB_URI in .env)",
        }
    try:
        from pymongo import MongoClient

        client = MongoClient(uri, serverSelectionTimeoutMS=8000)
        client.admin.command("ping")
        names = client[db_name].list_collection_names()
        return {
            "ok": True,
            "uri_kind": mongodb_uri_kind(uri),
            "database": db_name,
            "collections": sorted(names),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "uri_kind": mongodb_uri_kind(uri),
            "database": db_name,
            "error": str(exc),
            "hint": "For Atlas: allow network access from this machine/container; "
            "confirm MONGODB_URI + MIGRATION_TARGET_DB in .env.",
        }
