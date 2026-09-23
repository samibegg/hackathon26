"""Headless migration CLI (--skip-llm demo path)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from agent_rdbms_migration_poc.migration.ddl_parser import inventory_from_ddl
from agent_rdbms_migration_poc.migration.examples import read_example_ddl
from agent_rdbms_migration_poc.migration.plan import (
    build_ecommerce_migration_plan,
    canonical_ecommerce_schema_design,
)
from agent_rdbms_migration_poc.migration.runner import run_migration, run_validation


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Run deterministic Postgres → MongoDB migration")
    parser.add_argument(
        "--plan",
        type=Path,
        help="Optional path to a migration-plan.json; defaults to the generated e-commerce plan",
    )
    parser.add_argument("--skip-llm", action="store_true", help="No-op flag for demo scripts")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    if args.plan:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
    else:
        _, ddl = read_example_ddl("ecommerce_mvp")
        plan = build_ecommerce_migration_plan(
            inventory_from_ddl(ddl), canonical_ecommerce_schema_design()
        )
    if args.validate_only:
        report = run_validation(plan)
    else:
        stats = run_migration(plan)
        report = {"migration_stats": stats, "validation": run_validation(plan)}

    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    if isinstance(report, dict) and report.get("passed") is False:
        sys.exit(1)
    if isinstance(report, dict) and report.get("validation", {}).get("passed") is False:
        sys.exit(1)


if __name__ == "__main__":
    main()
