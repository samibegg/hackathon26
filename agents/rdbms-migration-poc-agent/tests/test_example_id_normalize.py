from agent_rdbms_migration_poc.migration.examples import get_example, normalize_example_id


def test_normalize_simple_phrases() -> None:
    assert normalize_example_id("simple three table") == "simple_three_table"
    assert get_example("simple three table").id == "simple_three_table"
