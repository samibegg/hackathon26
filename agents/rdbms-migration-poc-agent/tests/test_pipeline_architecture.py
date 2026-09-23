from agent_rdbms_migration_poc.migration.pipeline_architecture import build_pipeline_architecture
from agent_rdbms_migration_poc.migration.plan import canonical_ecommerce_schema_design
from agent_rdbms_migration_poc.migration.plan import build_ecommerce_migration_plan


def test_ecommerce_pipeline_architecture_describes_embed_and_validation() -> None:
    inventory = {
        "tables": [
            {"name": name}
            for name in ("customers", "products", "orders", "order_items", "payments")
        ]
    }
    plan = build_ecommerce_migration_plan(inventory, canonical_ecommerce_schema_design())
    architecture = build_pipeline_architecture(plan)

    assert [stage["name"] for stage in architecture["stages"]] == [
        "extract",
        "transform",
        "load",
        "validate",
    ]
    assert architecture["stages"][1]["embeddings"] == [
        {"child_table": "order_items", "array_field": "line_items"}
    ]
    assert "Change data capture and continuous synchronization." in architecture["out_of_scope"]
