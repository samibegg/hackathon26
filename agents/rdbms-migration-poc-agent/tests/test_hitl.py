import json

import pytest

from agent_rdbms_migration_poc.hitl import format_discovery_review_prompt, normalize_hitl_answer


def test_natural_language_approved() -> None:
    out = normalize_hitl_answer("Approved — proceed to schema design.")
    assert out["decision"] == "approved"
    assert "Approved" in out["reviewer_notes"]


def test_natural_language_rejected() -> None:
    out = normalize_hitl_answer("Rejected — need Postgres row counts first.")
    assert out["decision"] == "rejected"


def test_legacy_json_object() -> None:
    out = normalize_hitl_answer(
        {"decision": "approved", "reviewer_notes": "Discovery intake accepted."}
    )
    assert out["decision"] == "approved"


def test_legacy_json_string() -> None:
    raw = json.dumps({"decision": "approved", "reviewer_notes": "ok"})
    out = normalize_hitl_answer(raw)
    assert out["decision"] == "approved"


def test_empty_raises() -> None:
    with pytest.raises(ValueError):
        normalize_hitl_answer("   ")


def test_discovery_prompt_is_markdown_not_json_schema() -> None:
    text = format_discovery_review_prompt(
        summary="All ten areas covered.",
        completeness_score=1.0,
        gaps="None.",
    )
    assert "## Discovery review" in text
    assert "response_schema" not in text
    assert "Approved" in text


def test_incomplete_discovery_prompt_requires_explicit_waiver() -> None:
    text = format_discovery_review_prompt(
        summary="Several areas are missing.",
        completeness_score=0.7,
        gaps="Recovery objectives are unknown.",
    )
    assert "Approved with waiver" in text
