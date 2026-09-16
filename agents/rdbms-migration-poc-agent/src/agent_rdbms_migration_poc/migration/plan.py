"""Migration plan schema helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_plan(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def demo_reference_plan_path() -> Path:
    return Path(__file__).resolve().parents[3] / "demo" / "migration-plan.reference.json"


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
