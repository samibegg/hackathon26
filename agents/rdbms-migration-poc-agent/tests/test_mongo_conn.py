from agent_rdbms_migration_poc.migration.mongo_conn import (
    mongodb_uri_kind,
    resolve_migration_mongodb_uri,
)


def test_prefers_atlas_from_dotenv_over_local_process_uri(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/\n"
        "MIGRATION_TARGET_DB=commerce_poc\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "agent_rdbms_migration_poc.migration.mongo_conn.agent_root",
        lambda: tmp_path,
    )
    monkeypatch.setenv("MONGODB_URI", "mongodb://mongodb:27017/?directConnection=true")
    monkeypatch.delenv("MIGRATION_TARGET_MONGODB_URI", raising=False)

    uri = resolve_migration_mongodb_uri()
    assert mongodb_uri_kind(uri) == "atlas"
    assert uri.startswith("mongodb+srv://")


def test_explicit_migration_target_uri_wins(monkeypatch) -> None:
    monkeypatch.setenv("MIGRATION_TARGET_MONGODB_URI", "mongodb+srv://x:y@cluster.mongodb.net/")
    monkeypatch.setenv("MONGODB_URI", "mongodb://mongodb:27017")
    assert resolve_migration_mongodb_uri().startswith("mongodb+srv://")
