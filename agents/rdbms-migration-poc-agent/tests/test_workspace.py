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


def test_file_poc_pack_is_ordered_and_immutable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("MIGRATION_STATE_MONGODB_URI", raising=False)
    monkeypatch.delenv("MIGRATION_STATE_USE_MONGODB", raising=False)
    monkeypatch.setenv("MIGRATION_WORKSPACE_DIR", str(tmp_path))
    monkeypatch.setattr(ws, "session_key", lambda: "test-session-file")

    first = ws.record_poc_artifact("discovery_assessment", {"score": 0.8})
    second = ws.record_poc_artifact("source_inventory", {"tables": ["orders"]})

    assert first["sequence"] == 1
    assert second["sequence"] == 2
    assert first["content_sha256"] != second["content_sha256"]
    assert [record["kind"] for record in ws.get_poc_pack()] == [
        "discovery_assessment",
        "source_inventory",
    ]


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


def test_mongo_poc_pack_records_sequence_and_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIGRATION_STATE_MONGODB_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("MIGRATION_STATE_DB", "test_state_db")
    monkeypatch.setattr(ws, "session_key", lambda: "sess-abc")

    mock_artifacts = MagicMock()
    mock_workspace = MagicMock()
    mock_workspace.find_one_and_update.return_value = {"poc_pack_sequence": 3}
    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda name: {
        "migration_workspace": mock_workspace,
        "migration_poc_artifacts": mock_artifacts,
    }[name]
    mock_client = MagicMock()
    mock_client.__getitem__.return_value = mock_db

    with patch.object(ws, "_mongo_client", return_value=mock_client):
        record = ws.record_poc_artifact("validation_report", {"passed": True})

    assert record["sequence"] == 3
    assert len(record["content_sha256"]) == 64
    mock_artifacts.create_index.assert_called_once_with(
        [("session_id", 1), ("sequence", 1)], unique=True
    )
    mock_artifacts.insert_one.assert_called_once_with(record)


def test_mongo_poc_pack_catalog_groups_sessions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIGRATION_STATE_MONGODB_URI", "mongodb://localhost:27017")
    mock_artifacts = MagicMock()
    mock_artifacts.aggregate.return_value = [
        {"session_id": "previous-session", "artifact_count": 6, "latest_at": "2026-01-01T00:00:00Z"}
    ]
    mock_db = MagicMock()
    mock_db.__getitem__.return_value = mock_artifacts
    mock_client = MagicMock()
    mock_client.__getitem__.return_value = mock_db

    with patch.object(ws, "_mongo_client", return_value=mock_client):
        packs = ws.list_poc_packs()

    assert packs[0]["session_id"] == "previous-session"
    mock_artifacts.aggregate.assert_called_once()
