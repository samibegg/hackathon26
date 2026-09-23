from agent_rdbms_migration_poc.migration.mongo_conn import resolve_target_database


def test_target_database_uses_plan_default(monkeypatch) -> None:
    monkeypatch.delenv("MIGRATION_TARGET_DB", raising=False)
    assert resolve_target_database({"target": {"database": "from_plan"}}) == "from_plan"


def test_target_database_prefers_environment(monkeypatch) -> None:
    monkeypatch.setenv("MIGRATION_TARGET_DB", "from_environment")
    assert resolve_target_database({"target": {"database": "from_plan"}}) == "from_environment"
