from agent_rdbms_migration_poc.migration.discovery import (
    execution_gate_error,
    plan_generation_gate_error,
    schema_approval_error,
)


def test_plan_requires_scored_and_approved_discovery() -> None:
    assert plan_generation_gate_error(None, None) == {
        "error": "Discovery has not been scored. Call score_discovery_completeness first.",
    }
    assert plan_generation_gate_error({"completeness_score": 0.9}, None) == {
        "error": "Discovery is not approved. Complete HITL Gate 1 before generating a migration plan.",
        "completeness_score": 0.9,
    }


def test_plan_allows_approved_complete_discovery() -> None:
    assert plan_generation_gate_error(
        {"completeness_score": 0.8}, {"decision": "approved"}
    ) is None


def test_plan_requires_explicit_waiver_for_incomplete_discovery() -> None:
    score = {"completeness_score": 0.7}
    assert plan_generation_gate_error(score, {"decision": "approved"}) == {
        "error": "Discovery completeness is below 0.8 and has not been explicitly waived.",
        "completeness_score": 0.7,
        "required_approval": "Reply 'Approved with waiver' at HITL Gate 1, including reviewer notes.",
    }
    assert plan_generation_gate_error(
        score,
        {"decision": "approved", "waives_incomplete_discovery": True},
    ) is None


def test_execution_requires_approved_schema_after_discovery() -> None:
    score = {"completeness_score": 0.9}
    discovery = {"decision": "approved"}
    assert execution_gate_error(score, discovery, None) == {
        "error": "Target schema is not approved. Complete HITL Gate 2 before migration execution.",
    }
    assert execution_gate_error(score, discovery, {"decision": "approved"}) is None


def test_schema_approval_is_required_for_plan_generation() -> None:
    assert schema_approval_error(None, "generating a migration plan") == {
        "error": "Target schema is not approved. Complete HITL Gate 2 before generating a migration plan.",
    }
