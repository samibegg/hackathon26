import json

import pytest

from agent_rdbms_migration_poc.hitl import normalize_hitl_answer


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
