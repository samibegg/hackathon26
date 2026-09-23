"""Deterministic end-to-end migration demo with an Atlas-persisted PoC pack."""

from __future__ import annotations

import argparse
import json
import os
import uuid

from dotenv import load_dotenv

from agent_rdbms_migration_poc.migration.ddl_parser import inventory_from_ddl
from agent_rdbms_migration_poc.migration.cross_check import cross_check_transcript_with_inventory
from agent_rdbms_migration_poc.migration.discovery import score_transcript
from agent_rdbms_migration_poc.migration.examples import read_example_ddl
from agent_rdbms_migration_poc.migration.intake import fallback_structured_intake
from agent_rdbms_migration_poc.migration.mongo_conn import check_mongodb
from agent_rdbms_migration_poc.migration.plan import (
    build_ecommerce_migration_plan,
    canonical_ecommerce_schema_design,
)
from agent_rdbms_migration_poc.migration.pipeline_architecture import build_pipeline_architecture
from agent_rdbms_migration_poc.migration.postgres_conn import check_postgres
from agent_rdbms_migration_poc.migration.runner import run_migration, run_validation
from agent_rdbms_migration_poc.poc_pack import format_poc_pack_review
from agent_rdbms_migration_poc.workspace import get_poc_pack, record_poc_artifact


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", default="", help="Optional persisted PoC-pack session identifier")
    args = parser.parse_args()

    session_id = args.session_id or f"e2e-{uuid.uuid4()}"
    os.environ["MIGRATION_SESSION_ID"] = session_id
    postgres = check_postgres()
    if not postgres["ok"]:
        raise SystemExit(json.dumps(postgres, indent=2))
    mongo = check_mongodb()
    if not mongo["ok"]:
        raise SystemExit(json.dumps(mongo, indent=2))

    example, ddl = read_example_ddl("ecommerce_mvp")
    inventory = inventory_from_ddl(ddl)
    transcript = example.discovery_path.read_text(encoding="utf-8") if example.discovery_path else ""
    discovery = score_transcript(transcript)
    intake = fallback_structured_intake(transcript)
    cross_check = cross_check_transcript_with_inventory(transcript, inventory)
    design = canonical_ecommerce_schema_design()
    plan = build_ecommerce_migration_plan(inventory, design)
    architecture = build_pipeline_architecture(plan)

    record_poc_artifact("discovery_assessment", discovery)
    record_poc_artifact("structured_discovery_intake", intake)
    record_poc_artifact("source_inventory", inventory)
    record_poc_artifact("discovery_schema_cross_check", cross_check)
    record_poc_artifact(
        "hitl_discovery",
        {"decision": "approved", "reviewer_notes": "Automated end-to-end smoke test"},
    )
    record_poc_artifact("target_schema_design", design)
    record_poc_artifact(
        "hitl_schema",
        {"decision": "approved", "reviewer_notes": "Automated end-to-end smoke test"},
    )
    record_poc_artifact("field_mapping", plan["field_mappings"])
    record_poc_artifact("migration_plan", plan)
    record_poc_artifact("pipeline_architecture", architecture)
    record_poc_artifact(
        "hitl_execution",
        {"decision": "approved", "reviewer_notes": "Automated end-to-end smoke test"},
    )
    stats = run_migration(plan)
    report = run_validation(plan)
    record_poc_artifact("migration_execution", stats)
    record_poc_artifact("validation_report", report)

    result = {
        "session_id": session_id,
        "validation_passed": report["passed"],
        "review": format_poc_pack_review(get_poc_pack(session_id)),
    }
    print(json.dumps(result, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
