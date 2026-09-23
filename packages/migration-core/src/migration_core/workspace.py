"""Per-session workspace for migration artifacts.

Backends:
- **MongoDB** when ``MIGRATION_STATE_MONGODB_URI`` is set (optional fallback to ``MONGODB_URI``).
- **File** (``.mws`` under ``MIGRATION_WORKSPACE_DIR``) otherwise.

See ``docs/architecture.md`` for multi-agent state vs migration target ``MONGODB_URI``.
"""

from __future__ import annotations

import json
import os
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from agent_engine_runner_shared.context import get_current_payload, get_current_session_id

_PAYLOAD_TRANSCRIPT_KEYS = (
    "discovery_transcript",
    "transcript",
    "discovery_call_transcript",
)

_WORKSPACE_COLLECTION = "migration_workspace"


def session_key() -> str:
    sid = get_current_session_id()
    return sid if sid else "default"


def engagement_key() -> str:
    """Workspace document id — shared across intake and build agents."""
    payload = get_current_payload() or {}
    for key in ("engagement_id", "session_id"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    env_id = os.environ.get("ENGAGEMENT_ID", "").strip()
    if env_id:
        return env_id
    stored = _load_raw_key_from_current_doc_only()
    if stored:
        return stored
    return session_key()


def _load_raw_key_from_current_doc_only() -> str:
    """Avoid recursion: read engagement_id from file workspace only when using session file."""
    if resolve_state_mongodb_uri():
        return ""
    path = _workspace_dir() / f"{session_key()}.mws"
    if not path.is_file():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ""
    eid = data.get("engagement_id")
    return str(eid).strip() if eid else ""


def workspace_backend() -> Literal["mongodb", "file"]:
    return "mongodb" if resolve_state_mongodb_uri() else "file"


def resolve_state_mongodb_uri() -> str:
    """URI for PoC pack / multi-agent artifact state (not the migration data target)."""
    explicit = os.environ.get("MIGRATION_STATE_MONGODB_URI", "").strip()
    if explicit:
        return explicit
    if os.environ.get("MIGRATION_STATE_USE_MONGODB", "").strip().lower() in ("1", "true", "yes"):
        return os.environ.get("MONGODB_URI", "").strip()
    return ""


def state_database_name() -> str:
    return os.environ.get("MIGRATION_STATE_DB", "migration_poc_state").strip() or "migration_poc_state"


def _workspace_dir() -> Path:
    root = Path(os.environ.get("MIGRATION_WORKSPACE_DIR", ".agentic/migration-sessions"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def _workspace_file() -> Path:
    return _workspace_dir() / f"{engagement_key()}.mws"


def _load_file() -> dict[str, Any]:
    path = _workspace_file()
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_file(data: dict[str, Any]) -> None:
    _workspace_file().write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


@lru_cache(maxsize=1)
def _mongo_client():  # noqa: ANN202 — lazy singleton for dev
    from pymongo import MongoClient

    uri = resolve_state_mongodb_uri()
    if not uri:
        raise RuntimeError("MongoDB workspace requested but MIGRATION_STATE_MONGODB_URI is unset")
    return MongoClient(uri)


def _load_mongo() -> dict[str, Any]:
    client = _mongo_client()
    coll = client[state_database_name()][_WORKSPACE_COLLECTION]
    doc = coll.find_one({"_id": engagement_key()})
    if not doc:
        return {}
    return {k: v for k, v in doc.items() if k != "_id"}


def _save_mongo(data: dict[str, Any]) -> None:
    client = _mongo_client()
    coll = client[state_database_name()][_WORKSPACE_COLLECTION]
    coll.replace_one({"_id": engagement_key()}, {"_id": engagement_key(), **data}, upsert=True)


def _load() -> dict[str, Any]:
    if resolve_state_mongodb_uri():
        return _load_mongo()
    return _load_file()


def _save(data: dict[str, Any]) -> None:
    if resolve_state_mongodb_uri():
        _save_mongo(data)
    else:
        _save_file(data)


def workspace() -> dict[str, Any]:
    return _load()


def put_artifact(name: str, value: Any) -> None:
    ws = _load()
    ws[name] = value
    _save(ws)


def get_artifact(name: str, default: Any = None) -> Any:
    return _load().get(name, default)


def ensure_engagement_id() -> str:
    """Stable id for MongoDB workspace handoff between intake and build agents."""
    existing = get_artifact("engagement_id")
    if existing:
        return str(existing)
    sid = session_key()
    eid = sid if sid and sid != "default" else str(uuid.uuid4())
    put_artifact("engagement_id", eid)
    return eid


def resolve_discovery_transcript(explicit: str = "") -> str:
    """Resolve transcript from tool arg, session artifact, or Playground invocation payload."""
    if explicit.strip():
        put_artifact("discovery_transcript", explicit.strip())
        return explicit.strip()

    stored = str(get_artifact("discovery_transcript", ""))
    if stored.strip():
        return stored

    payload = get_current_payload() or {}
    for key in _PAYLOAD_TRANSCRIPT_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            put_artifact("discovery_transcript", value.strip())
            return value.strip()

    return ""
