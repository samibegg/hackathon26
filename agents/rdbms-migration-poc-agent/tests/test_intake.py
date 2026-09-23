from pathlib import Path

from agent_rdbms_migration_poc.migration.intake import extract_structured_intake, fallback_structured_intake


def test_fallback_intake_covers_all_discovery_areas() -> None:
    transcript = (Path(__file__).resolve().parents[1] / "demo" / "discovery_transcript.md").read_text()
    intake = fallback_structured_intake(transcript)

    assert intake["extraction_mode"] == "deterministic_fallback"
    assert len(intake["areas"]) == 10
    assert all(area["evidence"] for area in intake["areas"])


def test_llm_intake_normalizes_json_and_preserves_missing_areas() -> None:
    response = {
        "areas": [
            {
                "id": "context",
                "summary": "PoC targets lower join complexity.",
                "evidence": ["showing order history APIs"],
                "confidence": "high",
                "open_questions": ["Confirm latency target."],
            }
        ]
    }
    intake = extract_structured_intake("PoC goal is lower join complexity.", lambda _: response)

    assert intake["extraction_mode"] == "llm"
    assert intake["areas"][0]["summary"] == "PoC targets lower join complexity."
    assert len(intake["areas"]) == 10
    assert "Confirm latency target." in intake["open_questions"]


def test_invalid_llm_response_uses_fallback() -> None:
    intake = extract_structured_intake("We need a migration PoC.", lambda _: "not json")

    assert intake["extraction_mode"] == "deterministic_fallback"
