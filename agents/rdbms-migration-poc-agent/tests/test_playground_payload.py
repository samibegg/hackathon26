from pathlib import Path

from agent_rdbms_migration_poc.migration.discovery import score_transcript
from agent_rdbms_migration_poc.workspace import put_artifact, resolve_discovery_transcript


def test_playground_sample_payload_meets_gate() -> None:
    payload_path = Path(__file__).resolve().parents[1] / "demo" / "playground-sample-payload.json"
    import json

    data = json.loads(payload_path.read_text(encoding="utf-8"))
    text = data["discovery_transcript"]
    result = score_transcript(text)
    assert result["completeness_score"] >= 0.8


def test_resolve_discovery_transcript_prefers_explicit_arg() -> None:
    put_artifact("discovery_transcript", "stale")
    resolved = resolve_discovery_transcript("from tool arg")
    assert resolved == "from tool arg"
