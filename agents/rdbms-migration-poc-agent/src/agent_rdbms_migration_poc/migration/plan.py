"""Migration plan schema helpers."""

from __future__ import annotations

from typing import Any


def build_ecommerce_migration_plan(inventory: dict[str, Any], design: dict[str, Any]) -> dict[str, Any]:
    """Build the runner plan for the approved bundled e-commerce document design."""
    tables = {table.get("name") for table in inventory.get("tables", [])}
    required_tables = {"customers", "products", "orders", "order_items", "payments"}
    if not required_tables.issubset(tables):
        raise ValueError("MVP runner supports the 5-table e-commerce demo only.")

    collections = {collection.get("name"): collection for collection in design.get("collections", [])}
    orders = collections.get("orders", {})
    embedding = {
        (decision.get("child"), decision.get("parent"), decision.get("field"))
        for decision in design.get("embedding_decisions", [])
        if decision.get("decision") == "embed"
    }
    if orders.get("pattern") != "bucket_embed" or ("order_items", "orders", "line_items") not in embedding:
        raise ValueError("Approved schema must embed order_items as orders.line_items for the MVP runner.")

    return {
        "version": "1.0",
        "scenario": "ecommerce_order_management",
        "source": {"dialect": "postgresql", "database": "commerce_demo"},
        "target": {"database": "commerce_poc"},
        "collections": [
            {
                "name": "customers",
                "source_table": "customers",
                "pattern": "one_to_one",
                "primary_key": "customer_id",
                "indexes": [{"keys": {"email": 1}, "unique": True}],
            },
            {
                "name": "products",
                "source_table": "products",
                "pattern": "one_to_one",
                "primary_key": "product_id",
                "indexes": [{"keys": {"sku": 1}, "unique": True}],
            },
            {
                "name": "orders",
                "source_table": "orders",
                "pattern": "bucket_embed",
                "primary_key": "order_id",
                "embedded_children": [{"source_table": "order_items", "foreign_key": "order_id", "array_field": "line_items", "exclude_columns": ["order_id"]}],
                "indexes": [{"keys": {"customer_id": 1, "order_date": -1}}],
            },
            {
                "name": "payments",
                "source_table": "payments",
                "pattern": "one_to_one",
                "primary_key": "payment_id",
                "indexes": [{"keys": {"order_id": 1, "paid_at": -1}}],
            },
        ],
        "field_mappings": [
            {"source": "customers.customer_id", "target": "customers.customer_id"},
            {"source": "customers.email", "target": "customers.email"},
            {"source": "products.product_id", "target": "products.product_id"},
            {"source": "orders.order_id", "target": "orders.order_id"},
            {"source": "order_items.*", "target": "orders.line_items[]"},
            {"source": "payments.payment_id", "target": "payments.payment_id"},
        ],
        "validation": {
            "row_count_tables": ["customers", "products", "orders", "payments"],
            "embedded_integrity": {
                "parent_collection": "orders",
                "child_table": "order_items",
                "array_field": "line_items",
                "parent_key": "order_id",
            },
        },
    }


def canonical_ecommerce_schema_design() -> dict[str, Any]:
    """Target design for the bundled e-commerce demo."""
    return {
        "collections": [
            {
                "name": "customers",
                "pattern": "one_to_one",
                "rationale": "Customer master data; independent profile API.",
            },
            {
                "name": "products",
                "pattern": "one_to_one",
                "rationale": "Product catalog lookups; shared reference data.",
            },
            {
                "name": "orders",
                "pattern": "bucket_embed",
                "embedded": ["line_items"],
                "rationale": "Order history API always joins orders + order_items.",
            },
            {
                "name": "payments",
                "pattern": "one_to_one",
                "rationale": "Audit/compliance; queried separately from orders.",
            },
        ],
        "embedding_decisions": [
            {
                "child": "order_items",
                "parent": "orders",
                "field": "line_items",
                "decision": "embed",
                "evidence": "Discovery: order detail API always loads header + line items.",
            },
            {
                "child": "payments",
                "parent": "orders",
                "decision": "reference_separate_collection",
                "evidence": "Discovery: compliance requires isolated payment queries.",
            },
        ],
    }
