from pathlib import Path

from agent_rdbms_migration_poc.migration.discovery import score_transcript


def test_bundled_transcript_meets_completeness_gate() -> None:
    text = (Path(__file__).resolve().parents[1] / "demo" / "discovery_transcript.md").read_text()
    result = score_transcript(text)
    assert result["completeness_score"] >= 0.8
    assert result["ready_for_poc"] is True
