import json
from pathlib import Path

from agent_rdbms_migration_poc.migration.ddl_parser import inventory_from_ddl
from agent_rdbms_migration_poc.migration.examples import read_example_ddl
from agent_rdbms_migration_poc.migration.plan import (
    build_ecommerce_migration_plan,
    canonical_ecommerce_schema_design,
)


def test_ecommerce_plan_matches_reference() -> None:
    _, ddl = read_example_ddl("ecommerce_mvp")
    actual = build_ecommerce_migration_plan(inventory_from_ddl(ddl), canonical_ecommerce_schema_design())
    reference_path = Path(__file__).resolve().parents[1] / "demo" / "migration-plan.reference.json"
    assert actual == json.loads(reference_path.read_text(encoding="utf-8"))


def test_ecommerce_plan_rejects_unapproved_embedding_design() -> None:
    _, ddl = read_example_ddl("ecommerce_mvp")
    design = canonical_ecommerce_schema_design()
    design["collections"][2]["pattern"] = "one_to_one"

    try:
        build_ecommerce_migration_plan(inventory_from_ddl(ddl), design)
    except ValueError as error:
        assert "embed order_items" in str(error)
    else:
        raise AssertionError("Expected an incompatible schema design to be rejected")
