"""Per-session workspace for migration artifacts.

Backends:
- **MongoDB** when ``MIGRATION_STATE_MONGODB_URI`` is set (optional fallback to ``MONGODB_URI``).
- **File** (``.mws`` under ``MIGRATION_WORKSPACE_DIR``) otherwise.

See ``docs/architecture.md`` for multi-agent state vs migration target ``MONGODB_URI``.
"""

from __future__ import annotations

import json
import os
import hashlib
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from runner_shared.context import get_current_payload, get_current_session_id

_PAYLOAD_TRANSCRIPT_KEYS = (
    "discovery_transcript",
    "transcript",
    "discovery_call_transcript",
)

_WORKSPACE_COLLECTION = "migration_workspace"
_POC_ARTIFACT_COLLECTION = "migration_poc_artifacts"


def session_key() -> str:
    sid = get_current_session_id()
    if sid:
        return sid
    return os.environ.get("MIGRATION_SESSION_ID", "").strip() or "default"


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
    return _workspace_dir() / f"{session_key()}.mws"


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
    doc = coll.find_one({"_id": session_key()})
    if not doc:
        return {}
    return {k: v for k, v in doc.items() if k != "_id"}


def _save_mongo(data: dict[str, Any]) -> None:
    client = _mongo_client()
    coll = client[state_database_name()][_WORKSPACE_COLLECTION]
    coll.replace_one({"_id": session_key()}, {"_id": session_key(), **data}, upsert=True)


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


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def record_poc_artifact(kind: str, value: Any) -> dict[str, Any]:
    """Append an immutable PoC-pack artifact for traceability and later reuse."""
    payload = _json_safe(value)
    content = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    record = {
        "_id": str(uuid.uuid4()),
        "session_id": session_key(),
        "kind": kind,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "payload": payload,
    }
    if resolve_state_mongodb_uri():
        client = _mongo_client()
        coll = client[state_database_name()][_POC_ARTIFACT_COLLECTION]
        counter = client[state_database_name()][_WORKSPACE_COLLECTION].find_one_and_update(
            {"_id": session_key()},
            {"$inc": {"poc_pack_sequence": 1}},
            upsert=True,
            return_document=True,
        )
        record["sequence"] = counter["poc_pack_sequence"]
        coll.create_index([("session_id", 1), ("sequence", 1)], unique=True)
        coll.insert_one(record)
    else:
        ws = _load()
        pack = ws.setdefault("poc_pack", [])
        record["sequence"] = len(pack) + 1
        pack.append(record)
        _save(ws)
    return record


def get_poc_pack(session_id: str = "") -> list[dict[str, Any]]:
    """Return a session's immutable artifacts in workflow order."""
    key = session_id.strip() or session_key()
    if resolve_state_mongodb_uri():
        coll = _mongo_client()[state_database_name()][_POC_ARTIFACT_COLLECTION]
        return list(coll.find({"session_id": key}).sort("sequence", 1))
    if key != session_key():
        return []
    return _load().get("poc_pack", [])


def list_poc_packs(limit: int = 10) -> list[dict[str, Any]]:
    """List recent persisted packs for cross-session review and reuse."""
    if not resolve_state_mongodb_uri():
        pack = get_poc_pack()
        return (
            [{"session_id": session_key(), "artifact_count": len(pack), "latest_at": ""}]
            if pack
            else []
        )
    coll = _mongo_client()[state_database_name()][_POC_ARTIFACT_COLLECTION]
    pipeline = [
        {
            "$group": {
                "_id": "$session_id",
                "artifact_count": {"$sum": 1},
                "latest_at": {"$max": "$created_at"},
                "kinds": {"$addToSet": "$kind"},
            }
        },
        {"$sort": {"latest_at": -1}},
        {"$limit": limit},
        {"$project": {"_id": 0, "session_id": "$_id", "artifact_count": 1, "latest_at": 1, "kinds": 1}},
    ]
    return list(coll.aggregate(pipeline))


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
