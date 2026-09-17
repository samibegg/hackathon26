import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_rdbms_migration_poc import workspace as ws


@pytest.fixture(autouse=True)
def _clear_mongo_client_cache() -> None:
    ws._mongo_client.cache_clear()
    yield
    ws._mongo_client.cache_clear()


def test_file_backend_when_no_state_uri(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("MIGRATION_STATE_MONGODB_URI", raising=False)
    monkeypatch.delenv("MIGRATION_STATE_USE_MONGODB", raising=False)
    monkeypatch.setenv("MIGRATION_WORKSPACE_DIR", str(tmp_path))
    monkeypatch.setattr(ws, "session_key", lambda: "test-session-file")

    assert ws.workspace_backend() == "file"
    ws.put_artifact("flag", True)
    assert ws.get_artifact("flag") is True
    assert (tmp_path / "test-session-file.mws").is_file()


def test_mongo_backend_when_state_uri_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIGRATION_STATE_MONGODB_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("MIGRATION_STATE_DB", "test_state_db")
    monkeypatch.setattr(ws, "session_key", lambda: "sess-abc")

    store: dict[str, dict] = {}

    mock_coll = MagicMock()

    def replace_one(filter_doc: dict, doc: dict, upsert: bool = False) -> None:
        store[filter_doc["_id"]] = doc

    def find_one(filter_doc: dict) -> dict | None:
        return store.get(filter_doc["_id"])

    mock_coll.replace_one.side_effect = replace_one
    mock_coll.find_one.side_effect = find_one

    mock_db = MagicMock()
    mock_db.__getitem__.return_value = mock_coll
    mock_client = MagicMock()
    mock_client.__getitem__.return_value = mock_db

    with patch.object(ws, "_mongo_client", return_value=mock_client):
        assert ws.workspace_backend() == "mongodb"
        ws.put_artifact("discovery_score", {"completeness_score": 1.0})
        loaded = ws.get_artifact("discovery_score")
        assert loaded["completeness_score"] == 1.0
        mock_client.__getitem__.assert_called_with("test_state_db")
