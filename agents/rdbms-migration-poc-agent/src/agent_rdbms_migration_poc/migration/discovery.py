"""Discovery transcript completeness scoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DiscoveryArea:
    id: str
    title: str
    keywords: tuple[str, ...]


DISCOVERY_AREAS: tuple[DiscoveryArea, ...] = (
    DiscoveryArea("context", "Engagement context", ("success", "poc", "criteria", "goal")),
    DiscoveryArea("source_env", "Source environment", ("postgresql", "postgres", "database", "rds")),
    DiscoveryArea("schema_access", "Schema and access patterns", ("table", "join", "api", "access")),
    DiscoveryArea("apps", "Application landscape", ("application", "monolith", "service", "node")),
    DiscoveryArea("governance", "Data quality and governance", ("pii", "compliance", "governance", "quality")),
    DiscoveryArea("target_atlas", "Target MongoDB / Atlas", ("atlas", "mongodb", "cluster", "commerce_poc")),
    DiscoveryArea("model_prefs", "Model preferences", ("embed", "reference", "collection", "line_items")),
    DiscoveryArea("migration_approach", "Migration approach", ("bulk", "batch", "cutover", "cdc")),
    DiscoveryArea("validation", "Validation criteria", ("row count", "validation", "parity", "integrity")),
    DiscoveryArea("risks", "Risks and next steps", ("risk", "next step", "ddl", "assumption")),
)
DISCOVERY_COMPLETENESS_THRESHOLD = 0.8


def plan_generation_gate_error(
    discovery_score: Any, hitl_discovery: Any
) -> dict[str, Any] | None:
    """Return the Gate 1 failure that prevents migration plan generation, if any."""
    if not isinstance(discovery_score, dict):
        return {
            "error": "Discovery has not been scored. Call score_discovery_completeness first.",
        }

    score = discovery_score.get("completeness_score")
    if not isinstance(score, (int, float)):
        return {
            "error": "Discovery completeness score is invalid. Score discovery again before planning.",
        }

    if not isinstance(hitl_discovery, dict) or hitl_discovery.get("decision") != "approved":
        return {
            "error": "Discovery is not approved. Complete HITL Gate 1 before generating a migration plan.",
            "completeness_score": score,
        }

    if score < DISCOVERY_COMPLETENESS_THRESHOLD and not hitl_discovery.get(
        "waives_incomplete_discovery"
    ):
        return {
            "error": "Discovery completeness is below 0.8 and has not been explicitly waived.",
            "completeness_score": score,
            "required_approval": "Reply 'Approved with waiver' at HITL Gate 1, including reviewer notes.",
        }
    return None


def execution_gate_error(
    discovery_score: Any, hitl_discovery: Any, hitl_schema: Any
) -> dict[str, Any] | None:
    """Return the approval failure that prevents deterministic migration execution."""
    discovery_error = plan_generation_gate_error(discovery_score, hitl_discovery)
    if discovery_error:
        return discovery_error
    return schema_approval_error(hitl_schema, "migration execution")


def schema_approval_error(hitl_schema: Any, action: str) -> dict[str, Any] | None:
    """Return the Gate 2 failure that prevents an action based on target schema."""
    if not isinstance(hitl_schema, dict) or hitl_schema.get("decision") != "approved":
        return {"error": f"Target schema is not approved. Complete HITL Gate 2 before {action}."}
    return None


def score_transcript(transcript: str) -> dict:
    text = transcript.lower()
    areas = []
    for area in DISCOVERY_AREAS:
        hits = [kw for kw in area.keywords if kw in text]
        areas.append(
            {
                "id": area.id,
                "title": area.title,
                "covered": len(hits) > 0,
                "matched_keywords": hits,
            }
        )
    covered = sum(1 for a in areas if a["covered"])
    total = len(areas)
    score = round(covered / total, 2) if total else 0.0
    return {
        "completeness_score": score,
        "areas_covered": covered,
        "areas_total": total,
        "ready_for_poc": score >= DISCOVERY_COMPLETENESS_THRESHOLD,
        "areas": areas,
    }
