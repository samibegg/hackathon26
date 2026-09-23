"""Structured discovery intake extraction with a deterministic fallback."""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from agent_rdbms_migration_poc.migration.discovery import DISCOVERY_AREAS


def fallback_structured_intake(transcript: str) -> dict[str, Any]:
    """Extract evidence deterministically when an LLM is unavailable or untrusted."""
    sentences = re.split(r"(?<=[.!?])\s+|\n+", transcript.strip())
    areas = []
    for area in DISCOVERY_AREAS:
        evidence = [
            sentence.strip()
            for sentence in sentences
            if any(keyword in sentence.lower() for keyword in area.keywords)
        ][:3]
        areas.append(
            {
                "id": area.id,
                "title": area.title,
                "summary": evidence[0] if evidence else "Not established in the transcript.",
                "evidence": evidence,
                "confidence": "high" if evidence else "low",
                "open_questions": [] if evidence else [f"Clarify {area.title.lower()}."],
            }
        )
    return {
        "extraction_mode": "deterministic_fallback",
        "areas": areas,
        "open_questions": [question for area in areas for question in area["open_questions"]],
    }


def extract_structured_intake(
    transcript: str, invoke_llm: Callable[[str], Any] | None = None
) -> dict[str, Any]:
    """Use an LLM for structured intake, falling back to deterministic evidence extraction."""
    fallback = fallback_structured_intake(transcript)
    if invoke_llm is None:
        return fallback
    try:
        response = invoke_llm(_extraction_prompt(transcript))
        raw = getattr(response, "content", response)
        parsed = raw if isinstance(raw, dict) else json.loads(_json_text(raw))
        return _normalize_llm_intake(parsed, fallback)
    except Exception:  # noqa: BLE001 - a fallback must never block discovery review
        return fallback


def _extraction_prompt(transcript: str) -> str:
    area_list = ", ".join(area.id for area in DISCOVERY_AREAS)
    return f"""Extract a structured migration discovery intake from the transcript below.
Return JSON only with this shape:
{{"areas":[{{"id":"one of {area_list}","summary":"fact only","evidence":["verbatim quote"],"confidence":"high|medium|low","open_questions":["question"]}}]}}
Use only transcript evidence. Include every discovery area exactly once. Do not invent facts.

Transcript:
{transcript}"""


def _json_text(value: Any) -> str:
    text = value if isinstance(value, str) else str(value)
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    return text.strip()


def _normalize_llm_intake(value: Any, fallback: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict) or not isinstance(value.get("areas"), list):
        raise ValueError("Intake response is not an object with areas.")
    valid_ids = {item.id for item in DISCOVERY_AREAS}
    by_id = {
        str(area.get("id")): area
        for area in value["areas"]
        if isinstance(area, dict) and str(area.get("id")) in valid_ids
    }
    normalized = []
    for fallback_area in fallback["areas"]:
        candidate = by_id.get(fallback_area["id"])
        if not candidate:
            normalized.append(fallback_area)
            continue
        confidence = str(candidate.get("confidence", "medium")).lower()
        normalized.append(
            {
                "id": fallback_area["id"],
                "title": fallback_area["title"],
                "summary": str(candidate.get("summary", fallback_area["summary"])).strip(),
                "evidence": _string_list(candidate.get("evidence"))[:3],
                "confidence": confidence if confidence in {"high", "medium", "low"} else "medium",
                "open_questions": _string_list(candidate.get("open_questions")),
            }
        )
    return {
        "extraction_mode": "llm",
        "areas": normalized,
        "open_questions": [question for area in normalized for question in area["open_questions"]],
    }


def _string_list(value: Any) -> list[str]:
    return [str(item).strip() for item in value] if isinstance(value, list) else []
