"""Per-session workspace for migration artifacts (file-backed for aer + tool runtimes)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from runner_shared.context import get_current_payload, get_current_session_id

_PAYLOAD_TRANSCRIPT_KEYS = (
    "discovery_transcript",
    "transcript",
    "discovery_call_transcript",
)


def session_key() -> str:
    sid = get_current_session_id()
    return sid if sid else "default"


def _workspace_dir() -> Path:
    # Under .agentic/ so agentic dev file-watcher ignores writes (avoids hot-reload mid-chat).
    root = Path(os.environ.get("MIGRATION_WORKSPACE_DIR", ".agentic/migration-sessions"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def _workspace_file() -> Path:
    # Use a non-.json extension so dev file-watchers never treat session state as source.
    return _workspace_dir() / f"{session_key()}.mws"


def _load() -> dict[str, Any]:
    path = _workspace_file()
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save(data: dict[str, Any]) -> None:
    _workspace_file().write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def workspace() -> dict[str, Any]:
    return _load()


def put_artifact(name: str, value: Any) -> None:
    ws = _load()
    ws[name] = value
    _save(ws)


def get_artifact(name: str, default: Any = None) -> Any:
    return _load().get(name, default)


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
