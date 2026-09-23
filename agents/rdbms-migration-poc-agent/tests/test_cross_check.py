from pathlib import Path

from agent_rdbms_migration_poc.migration.cross_check import cross_check_transcript_with_inventory
from agent_rdbms_migration_poc.migration.ddl_parser import inventory_from_ddl


def test_bundled_transcript_and_ddl_pass_cross_check() -> None:
    root = Path(__file__).resolve().parents[1] / "demo"
    result = cross_check_transcript_with_inventory(
        (root / "discovery_transcript.md").read_text(),
        inventory_from_ddl((root / "schema.sql").read_text()),
    )

    assert result["status"] == "pass"
    assert result["entities_without_source_tables"] == []
    assert result["relationships"]["missing"] == []
    assert "customers.email" in result["sensitive_columns"]
    assert result["governance_mentioned"] is True


def test_cross_check_flags_unmodeled_entity_and_missing_relationship() -> None:
    inventory = {
        "tables": [
            {"name": "orders", "columns": [], "references": []},
            {"name": "order_items", "columns": [], "references": []},
        ]
    }
    result = cross_check_transcript_with_inventory(
        "Orders include line items and returns. Payments are queried by order_id.", inventory
    )

    assert result["status"] == "needs_review"
    assert "returns" in result["entities_without_source_tables"]
    assert {"child_table": "order_items", "parent_table": "orders"} in result["relationships"]["missing"]
