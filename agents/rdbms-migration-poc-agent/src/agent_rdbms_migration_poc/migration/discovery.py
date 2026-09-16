"""Discovery transcript completeness scoring."""

from __future__ import annotations

from dataclasses import dataclass


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
        "ready_for_poc": score >= 0.8,
        "areas": areas,
    }
