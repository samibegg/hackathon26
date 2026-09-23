"""Readable Playground review for persisted migration PoC artifacts."""

from __future__ import annotations

from typing import Any


_ARTIFACT_TITLES = {
    "discovery_assessment": "Discovery Assessment",
    "structured_discovery_intake": "Structured Discovery Intake",
    "source_inventory": "Source Inventory",
    "source_inventory_row_counts": "Source Inventory Row Counts",
    "discovery_schema_cross_check": "Discovery-to-Source Cross-Check",
    "hitl_discovery": "Discovery Approval",
    "target_schema_design": "Target Schema",
    "hitl_schema": "Schema Approval",
    "field_mapping": "Field Mapping",
    "migration_plan": "Migration Plan",
    "pipeline_architecture": "Pipeline Architecture",
    "hitl_execution": "Execution Approval",
    "migration_execution": "Migration Execution",
    "validation_report": "Validation Report",
}

_ARTIFACT_ORDER = tuple(_ARTIFACT_TITLES)


def format_poc_pack_review(records: list[dict[str, Any]]) -> str:
    """Render the latest version of each artifact as a compact Markdown review."""
    latest = {record.get("kind"): record for record in records if record.get("kind")}
    if not latest:
        return "# PoC Pack Review\n\nNo persisted artifacts exist for this session yet."

    lines = ["# PoC Pack Review", ""]
    for kind in _ARTIFACT_ORDER:
        record = latest.get(kind)
        if not record:
            continue
        lines.extend(_format_artifact(kind, record))
    return "\n".join(lines)


def format_poc_pack_catalog(packs: list[dict[str, Any]]) -> str:
    """Render reusable persisted pack identifiers without exposing their contents."""
    if not packs:
        return "No other persisted PoC packs are available."
    lines = ["## Available Persisted PoC Packs", ""]
    for pack in packs:
        lines.append(
            f"- `{pack.get('session_id')}`: {pack.get('artifact_count', 0)} artifacts, "
            f"latest {pack.get('latest_at', 'unknown time')}"
        )
    lines.extend(["", "Use `get_poc_pack_review` with a session ID to review a prior pack."])
    return "\n".join(lines)


def _format_artifact(kind: str, record: dict[str, Any]) -> list[str]:
    payload = record.get("payload", {})
    metadata = (
        f"Recorded {record.get('created_at', 'unknown time')} | "
        f"trace {str(record.get('content_sha256', ''))[:12]}"
    )
    lines = [f"## {_ARTIFACT_TITLES[kind]}", metadata, ""]

    if kind == "discovery_assessment":
        lines.append(
            f"Completeness: **{payload.get('completeness_score', 'unknown')}** "
            f"({payload.get('areas_covered', 0)}/{payload.get('areas_total', 0)} areas)"
        )
    elif kind == "structured_discovery_intake":
        lines.append(f"Extraction: **{payload.get('extraction_mode', 'unknown')}**")
        for area in payload.get("areas", []):
            lines.append(
                f"- {area.get('title')}: {area.get('confidence', 'unknown')} confidence - {area.get('summary')}"
            )
        questions = payload.get("open_questions", [])
        if questions:
            lines.append("Open questions: " + "; ".join(questions))
    elif kind.startswith("source_inventory"):
        inventory = payload.get("inventory", payload)
        tables = [table.get("name") for table in inventory.get("tables", [])]
        counts = inventory.get("row_counts", {})
        lines.append(f"Tables: {', '.join(tables) or 'none'}")
        if counts:
            lines.append("Row counts: " + ", ".join(f"{name}={count}" for name, count in counts.items()))
        flags = payload.get("risk_flags", {})
        if flags.get("missing_demo_tables"):
            lines.append("Risks: missing " + ", ".join(flags["missing_demo_tables"]))
    elif kind == "discovery_schema_cross_check":
        lines.append(f"Result: **{str(payload.get('status', 'unknown')).upper()}**")
        missing = payload.get("entities_without_source_tables", [])
        if missing:
            lines.append("Unmatched entities: " + ", ".join(missing))
        relationships = payload.get("relationships", {})
        if relationships.get("missing"):
            lines.append("Missing relationships: " + ", ".join(
                f"{item['child_table']} -> {item['parent_table']}" for item in relationships["missing"]
            ))
        if payload.get("sensitive_columns"):
            lines.append("Sensitive fields: " + ", ".join(payload["sensitive_columns"]))
        lines.extend(f"Assumption: {item}" for item in payload.get("assumptions", []))
    elif kind.startswith("hitl_"):
        lines.append(f"Decision: **{payload.get('decision', 'unknown')}**")
        if payload.get("reviewer_notes"):
            lines.append(f"Notes: {payload['reviewer_notes']}")
    elif kind == "target_schema_design":
        collections = payload.get("collections", [])
        lines.append("Collections: " + ", ".join(item.get("name", "unknown") for item in collections))
        for decision in payload.get("embedding_decisions", []):
            lines.append(
                f"{decision.get('child')} -> {decision.get('parent')}: {decision.get('decision')}"
            )
    elif kind == "field_mapping":
        lines.extend(
            f"- `{mapping.get('source')}` -> `{mapping.get('target')}`" for mapping in payload
        )
    elif kind == "migration_plan":
        lines.append(f"Target database: `{payload.get('target', {}).get('database', 'unknown')}`")
        lines.append(
            "Collections: " + ", ".join(item.get("name", "unknown") for item in payload.get("collections", []))
        )
    elif kind == "pipeline_architecture":
        lines.append("Flow: " + " -> ".join(stage.get("name", "unknown") for stage in payload.get("stages", [])))
        load_stage = next(
            (stage for stage in payload.get("stages", []) if stage.get("name") == "load"), {}
        )
        lines.append(
            "Target: `"
            + str(payload.get("source", {}).get("database", "unknown"))
            + "` -> `"
            + str(load_stage.get("target_database", "unknown"))
            + "`"
        )
        lines.append("Out of scope: " + "; ".join(payload.get("out_of_scope", [])))
    elif kind == "migration_execution":
        written = payload.get("collections_written", {})
        lines.append("Documents written: " + ", ".join(f"{name}={count}" for name, count in written.items()))
    elif kind == "validation_report":
        checks = payload.get("checks", [])
        lines.append(f"Result: **{'PASS' if payload.get('passed') else 'FAIL'}** ({len(checks)} checks)")
        lines.extend(
            f"- {'PASS' if check.get('passed') else 'FAIL'}: {check.get('check', 'unknown')}"
            for check in checks
        )

    lines.append("")
    return lines
