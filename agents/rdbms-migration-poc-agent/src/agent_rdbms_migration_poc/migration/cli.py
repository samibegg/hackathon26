"""Headless migration CLI (--skip-llm demo path)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from agent_rdbms_migration_poc.migration.plan import demo_reference_plan_path, load_plan
from agent_rdbms_migration_poc.migration.runner import run_migration, run_validation


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Run deterministic Postgres → MongoDB migration")
    parser.add_argument(
        "--plan",
        type=Path,
        default=demo_reference_plan_path(),
        help="Path to migration-plan.json",
    )
    parser.add_argument("--skip-llm", action="store_true", help="No-op flag for demo scripts")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    plan = load_plan(args.plan)
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
