"""Bundled PostgreSQL DDL examples."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from migration_core.paths import agent_root


def normalize_example_id(raw: str) -> str:
    """Map human-friendly names to canonical example ids."""
    key = raw.strip().lower().replace("-", "_")
    key = "_".join(key.split())
    aliases = {
        "simple": "simple_three_table",
        "simple_three_table": "simple_three_table",
        "three_table": "simple_three_table",
        "simple_three_table_example": "simple_three_table",
        "ecommerce": "ecommerce_mvp",
        "ecommerce_mvp": "ecommerce_mvp",
        "full": "ecommerce_mvp",
        "bundled": "ecommerce_mvp",
    }
    return aliases.get(key, key)


@dataclass(frozen=True)
class DdlExample:
    id: str
    title: str
    description: str
    supports_deterministic_migration: bool
    ddl_path: Path
    discovery_path: Path | None = None


def _examples_root() -> Path:
    return agent_root() / "demo" / "examples"


def _agent_demo_root() -> Path:
    return agent_root() / "demo"


EXAMPLES: dict[str, DdlExample] = {
    "simple_three_table": DdlExample(
        id="simple_three_table",
        title="Simple three-table orders",
        description="customers + orders + order_lines — DDL parse and design only.",
        supports_deterministic_migration=False,
        ddl_path=_examples_root() / "simple_three_table" / "schema.sql",
        discovery_path=_examples_root() / "simple_three_table" / "discovery_snippet.md",
    ),
    "ecommerce_mvp": DdlExample(
        id="ecommerce_mvp",
        title="E-commerce MVP (5 tables)",
        description="Full PoC: customers, products, orders, order_items, payments.",
        supports_deterministic_migration=True,
        ddl_path=_agent_demo_root() / "schema.sql",
        discovery_path=_agent_demo_root() / "discovery_transcript.md",
    ),
}


def list_examples() -> list[dict]:
    return [
        {
            "id": ex.id,
            "title": ex.title,
            "description": ex.description,
            "supports_deterministic_migration": ex.supports_deterministic_migration,
            "table_count_hint": "3" if ex.id == "simple_three_table" else "5",
        }
        for ex in EXAMPLES.values()
    ]


def get_example(example_id: str) -> DdlExample:
    canonical = normalize_example_id(example_id)
    if canonical not in EXAMPLES:
        raise KeyError(
            f"Unknown example {example_id!r} (normalized: {canonical!r}). "
            "Use list_ddl_examples for ids."
        )
    return EXAMPLES[canonical]


def read_example_ddl(example_id: str) -> tuple[DdlExample, str]:
    ex = get_example(example_id)
    if not ex.ddl_path.is_file():
        raise FileNotFoundError(
            f"DDL file missing at {ex.ddl_path}. "
            "Ensure demo/examples is present in the agent directory."
        )
    return ex, ex.ddl_path.read_text(encoding="utf-8")


def simple_three_table_schema_design() -> dict:
    """MongoDB target design for demo/examples/simple_three_table."""
    return {
        "example_id": "simple_three_table",
        "collections": [
            {
                "name": "customers",
                "pattern": "one_to_one",
                "source_table": "customers",
                "rationale": "Customer profile API reads master data only.",
            },
            {
                "name": "orders",
                "pattern": "bucket_embed",
                "source_table": "orders",
                "embedded": ["line_items"],
                "rationale": "Order detail API always loads header + order_lines together.",
            },
        ],
        "field_mappings": [
            {"source": "customers.customer_id", "target": "customers.customer_id"},
            {"source": "customers.email", "target": "customers.email"},
            {"source": "orders.order_id", "target": "orders.order_id"},
            {"source": "order_lines.line_id", "target": "orders.line_items[].line_id"},
            {"source": "order_lines.sku", "target": "orders.line_items[].sku"},
        ],
        "indexes": [
            {"collection": "customers", "keys": {"email": 1}, "unique": True},
            {"collection": "orders", "keys": {"customer_id": 1, "order_date": -1}},
        ],
        "note": "Design-only example — use ecommerce_mvp for execute_migration_pipeline.",
    }
