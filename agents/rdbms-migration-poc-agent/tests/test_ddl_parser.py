from pathlib import Path

from agent_rdbms_migration_poc.migration.ddl_parser import inventory_from_ddl


def test_demo_ddl_parses_five_tables() -> None:
    ddl = (Path(__file__).resolve().parents[1] / "demo" / "schema.sql").read_text()
    inv = inventory_from_ddl(ddl)
    names = {t["name"] for t in inv["tables"]}
    assert names == {"customers", "products", "orders", "order_items", "payments"}
