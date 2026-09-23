from agent_rdbms_migration_poc.poc_pack import format_poc_pack_catalog, format_poc_pack_review


def test_review_renders_latest_artifacts_in_workflow_order() -> None:
    records = [
        {
            "kind": "validation_report",
            "created_at": "2026-01-01T00:00:00+00:00",
            "content_sha256": "c" * 64,
            "payload": {"passed": True, "checks": [{"check": "row_count", "passed": True}]},
        },
        {
            "kind": "discovery_assessment",
            "created_at": "2026-01-01T00:00:00+00:00",
            "content_sha256": "a" * 64,
            "payload": {"completeness_score": 0.9, "areas_covered": 9, "areas_total": 10},
        },
        {
            "kind": "migration_execution",
            "created_at": "2026-01-01T00:00:00+00:00",
            "content_sha256": "b" * 64,
            "payload": {"collections_written": {"orders": 5000}},
        },
    ]

    review = format_poc_pack_review(records)

    assert review.index("## Discovery Assessment") < review.index("## Migration Execution")
    assert review.index("## Migration Execution") < review.index("## Validation Report")
    assert "Completeness: **0.9** (9/10 areas)" in review
    assert "Documents written: orders=5000" in review
    assert "Result: **PASS** (1 checks)" in review


def test_review_handles_empty_pack() -> None:
    assert format_poc_pack_review([]) == "# PoC Pack Review\n\nNo persisted artifacts exist for this session yet."


def test_catalog_lists_reusable_sessions() -> None:
    catalog = format_poc_pack_catalog(
        [{"session_id": "prior-session", "artifact_count": 8, "latest_at": "2026-01-01T00:00:00Z"}]
    )

    assert "`prior-session`: 8 artifacts" in catalog
    assert "get_poc_pack_review" in catalog


def test_review_renders_pipeline_architecture() -> None:
    review = format_poc_pack_review(
        [
            {
                "kind": "pipeline_architecture",
                "created_at": "2026-01-01T00:00:00+00:00",
                "content_sha256": "d" * 64,
                "payload": {
                    "source": {"database": "commerce_demo"},
                    "stages": [
                        {"name": "extract"},
                        {"name": "transform"},
                        {"name": "load", "target_database": "commerce_poc"},
                        {"name": "validate"},
                    ],
                    "out_of_scope": ["Change data capture."],
                },
            }
        ]
    )

    assert "Flow: extract -> transform -> load -> validate" in review
    assert "`commerce_demo` -> `commerce_poc`" in review
