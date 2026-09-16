from agent_rdbms_migration_poc.migration.ddl_parser import inventory_from_ddl
from agent_rdbms_migration_poc.migration.examples import get_example, list_examples


def test_list_includes_simple_and_ecommerce() -> None:
    ids = {e["id"] for e in list_examples()}
    assert "simple_three_table" in ids
    assert "ecommerce_mvp" in ids


def test_simple_example_ddl_parses_three_tables() -> None:
    ex = get_example("simple_three_table")
    inv = inventory_from_ddl(ex.ddl_path.read_text())
    assert inv["table_count"] == 3
    assert {t["name"] for t in inv["tables"]} == {"customers", "orders", "order_lines"}
