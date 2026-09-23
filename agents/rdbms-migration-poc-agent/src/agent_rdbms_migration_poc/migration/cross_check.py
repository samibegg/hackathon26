"""Deterministic discovery transcript and source-inventory cross-checks."""

from __future__ import annotations

import re
from typing import Any


_ENTITY_ALIASES = {
    "customers": ("customer", "customers", "customer profile"),
    "products": ("product", "products", "catalog"),
    "orders": ("order", "orders", "order history", "order header"),
    "order_items": ("order item", "order items", "line item", "line items"),
    "payments": ("payment", "payments"),
}
_UNMODELED_ENTITY_ALIASES = ("address", "addresses", "shipment", "shipments", "return", "returns", "invoice", "invoices")
_SENSITIVE_COLUMN_HINTS = ("email", "name", "payment", "card", "ssn", "phone", "address")
_RELATIONSHIP_HINTS = (
    ("order_items", "orders", ("line item", "order")),
    ("payments", "orders", ("payment", "order_id")),
)


def cross_check_transcript_with_inventory(transcript: str, inventory: dict[str, Any]) -> dict[str, Any]:
    """Compare transcript evidence with source tables, FKs, and sensitive columns."""
    text = transcript.lower()
    tables = {str(table.get("name", "")): table for table in inventory.get("tables", [])}
    mentioned = sorted(
        table
        for table, aliases in _ENTITY_ALIASES.items()
        if any(_contains_phrase(text, alias) for alias in aliases)
    )
    unmodeled = sorted(
        entity for entity in _UNMODELED_ENTITY_ALIASES if _contains_phrase(text, entity)
    )
    missing_entities = sorted(set(mentioned) - set(tables))
    unmentioned_tables = sorted(set(tables) - set(mentioned))
    actual_relationships = {
        (table_name, str(reference.get("table", "")))
        for table_name, table in tables.items()
        for reference in table.get("references", [])
    }
    expected_relationships = [
        (child, parent)
        for child, parent, terms in _RELATIONSHIP_HINTS
        if all(_contains_phrase(text, term) for term in terms)
    ]
    missing_relationships = [
        {"child_table": child, "parent_table": parent} for child, parent in expected_relationships if (child, parent) not in actual_relationships
    ]
    verified_relationships = [
        {"child_table": child, "parent_table": parent} for child, parent in expected_relationships if (child, parent) in actual_relationships
    ]
    sensitive_columns = [
        f"{table_name}.{column.get('name')}"
        for table_name, table in tables.items()
        for column in table.get("columns", [])
        if any(hint in str(column.get("name", "")).lower() for hint in _SENSITIVE_COLUMN_HINTS)
    ]
    governance_mentioned = any(term in text for term in ("pii", "governance", "compliance", "retain"))
    assumptions = []
    if unmentioned_tables:
        assumptions.append("Confirm whether source tables not mentioned in discovery are in scope.")
    if sensitive_columns and not governance_mentioned:
        assumptions.append("Confirm handling and retention requirements for sensitive source fields.")
    if unmodeled:
        assumptions.append("Confirm whether discovery entities without matching source tables are out of scope.")
    risks = []
    if missing_entities:
        risks.append({"severity": "high", "detail": "Discovery entities have no matching source table."})
    if missing_relationships:
        risks.append({"severity": "high", "detail": "Discovery-implied relationships are missing foreign keys."})
    if sensitive_columns:
        risks.append(
            {
                "severity": "info" if governance_mentioned else "medium",
                "detail": "Sensitive or payment-related source fields require confirmed handling.",
            }
        )
    return {
        "status": "pass" if not missing_entities and not missing_relationships else "needs_review",
        "mentioned_entities": mentioned,
        "entities_without_source_tables": missing_entities + unmodeled,
        "source_tables_not_discussed": unmentioned_tables,
        "relationships": {"verified": verified_relationships, "missing": missing_relationships},
        "sensitive_columns": sensitive_columns,
        "governance_mentioned": governance_mentioned,
        "risks": risks,
        "assumptions": assumptions,
    }


def _contains_phrase(text: str, phrase: str) -> bool:
    return bool(re.search(rf"\b{re.escape(phrase)}s?\b", text))
