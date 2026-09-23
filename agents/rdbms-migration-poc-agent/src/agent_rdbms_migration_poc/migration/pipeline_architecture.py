"""Deterministic extract-transform-load-validate architecture artifact."""

from __future__ import annotations

from typing import Any


def build_pipeline_architecture(plan: dict[str, Any]) -> dict[str, Any]:
    """Describe the deterministic runner architecture for an approved migration plan."""
    collections = plan.get("collections", [])
    embedded = [
        child
        for collection in collections
        for child in collection.get("embedded_children", [])
    ]
    return {
        "source": {
            "system": "PostgreSQL",
            "database": plan.get("source", {}).get("database"),
            "tables": [collection.get("source_table") for collection in collections]
            + [child.get("source_table") for child in embedded],
        },
        "stages": [
            {
                "name": "extract",
                "description": "Read the approved source tables with deterministic SELECT queries.",
            },
            {
                "name": "transform",
                "description": "Convert scalar values to JSON-safe types and embed approved child rows.",
                "embeddings": [
                    {
                        "child_table": child.get("source_table"),
                        "array_field": child.get("array_field"),
                    }
                    for child in embedded
                ],
            },
            {
                "name": "load",
                "description": "Replace demo target collections and create plan-defined indexes.",
                "target_database": plan.get("target", {}).get("database"),
                "collections": [collection.get("name") for collection in collections],
            },
            {
                "name": "validate",
                "description": "Reconcile source row counts and embedded child integrity.",
                "checks": plan.get("validation", {}),
            },
        ],
        "safety": [
            "Execution requires approved discovery, schema, and execution gates.",
            "The runner replaces only collections declared in the approved migration plan.",
            "Validation runs immediately after loading and records a traceable report.",
        ],
        "out_of_scope": [
            "Change data capture and continuous synchronization.",
            "Production cutover and rollback orchestration.",
            "Production retry, monitoring, and alerting policies.",
        ],
    }
