"""Migration PoC tools — deterministic execution, LLM-assisted orchestration."""

from __future__ import annotations

import json
import os
from typing import Any

import psycopg
from langgraph.types import interrupt
from agent_engine_sdk_langgraph import App

from agent_rdbms_migration_poc.migration.ddl_parser import inventory_from_ddl
from agent_rdbms_migration_poc.migration.discovery import score_transcript
from agent_rdbms_migration_poc.migration.examples import (
    get_example,
    list_examples,
    normalize_example_id,
    read_example_ddl,
    simple_three_table_schema_design,
)
from agent_rdbms_migration_poc.migration.plan import (
    canonical_ecommerce_schema_design,
    demo_reference_plan_path,
    load_plan,
)
from agent_rdbms_migration_poc.migration.mongo_conn import (
    check_mongodb,
    mongodb_uri_kind,
    resolve_migration_mongodb_uri,
    resolve_migration_target_db,
)
from agent_rdbms_migration_poc.migration.postgres_conn import check_postgres, resolve_postgres_uri
from agent_rdbms_migration_poc.hitl import (
    format_discovery_review_prompt,
    format_execution_review_prompt,
    format_schema_review_prompt,
    normalize_hitl_answer,
)
from agent_rdbms_migration_poc.migration.runner import run_migration, run_validation
from agent_rdbms_migration_poc.workspace import (
    get_artifact,
    put_artifact,
    resolve_discovery_transcript,
    workspace,
)

DEMO_TABLES = frozenset({"customers", "products", "orders", "order_items", "payments"})


def _await_hitl_approval(prompt: str) -> dict[str, str]:
    """Suspend for architect input; Playground shows ``prompt`` as markdown/text."""
    raw = interrupt(prompt)
    try:
        return normalize_hitl_answer(raw)
    except ValueError as err:
        raise ValueError(
            f"{err}. Reply with e.g. 'Approved' or 'Rejected — reason'."
        ) from err


def register(app: App) -> None:
    def _load_example_into_workspace(example_id: str) -> dict[str, Any]:
        canonical = normalize_example_id(example_id)
        try:
            ex, ddl = read_example_ddl(canonical)
        except KeyError as err:
            return {"error": str(err), "hint": "Call list_ddl_examples for valid ids."}
        except FileNotFoundError as err:
            return {"error": str(err)}
        put_artifact("ddl_text", ddl)
        put_artifact("ddl_example_id", ex.id)
        if ex.discovery_path and ex.discovery_path.is_file():
            put_artifact("discovery_transcript", ex.discovery_path.read_text(encoding="utf-8"))
        return {
            "status": "loaded",
            "example_id": ex.id,
            "title": ex.title,
            "ddl_chars": len(ddl),
            "supports_deterministic_migration": ex.supports_deterministic_migration,
        }

    def _parse_ddl_in_workspace() -> dict[str, Any]:
        text = str(get_artifact("ddl_text", ""))
        if not text.strip():
            return {"error": "No DDL in workspace. Call load_ddl_example first."}
        inventory = inventory_from_ddl(text)
        put_artifact("source_inventory", inventory)
        table_names = {t["name"] for t in inventory["tables"]}
        put_artifact(
            "ddl_risk_flags",
            {
                "missing_demo_tables": sorted(DEMO_TABLES - table_names),
                "unexpected_tables": sorted(table_names - DEMO_TABLES),
                "mvp_table_count_ok": DEMO_TABLES.issubset(table_names),
            },
        )
        return inventory

    def _propose_design_in_workspace() -> dict[str, Any]:
        example_id = str(get_artifact("ddl_example_id", "ecommerce_mvp"))
        if example_id == "simple_three_table":
            design = simple_three_table_schema_design()
        else:
            design = canonical_ecommerce_schema_design()
        put_artifact("target_schema_design", design)
        return design

    def _generate_plan_in_workspace() -> dict[str, Any]:
        inventory = get_artifact("source_inventory", {})
        table_names = {t["name"] for t in inventory.get("tables", [])}
        example_id = str(get_artifact("ddl_example_id", ""))
        if example_id == "simple_three_table":
            return {
                "error": "No migration-plan runner for simple_three_table (design-only example).",
                "hint": "Use ecommerce_mvp for execute_migration_pipeline.",
            }
        if DEMO_TABLES.issubset(table_names):
            plan = load_plan(demo_reference_plan_path())
            put_artifact("migration_plan", plan)
            return plan
        return {
            "error": "MVP runner supports the 5-table e-commerce demo only.",
            "found_tables": sorted(table_names),
            "required_tables": sorted(DEMO_TABLES),
        }

    def _attach_row_counts(inventory: dict[str, Any]) -> dict[str, Any]:
        postgres_uri = resolve_postgres_uri()
        if not postgres_uri:
            return inventory
        counts: dict[str, int] = {}
        with psycopg.connect(postgres_uri, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                for table in inventory.get("tables", []):
                    name = table["name"]
                    cur.execute(f'SELECT COUNT(*) FROM "{name}"')  # noqa: S608
                    counts[name] = int(cur.fetchone()[0])
        enriched = {**inventory, "row_counts": counts}
        put_artifact("source_inventory", enriched)
        return enriched

    @app.tool()
    def check_postgres_connection() -> str:
        """Verify demo Postgres is reachable from this runtime (POSTGRES_URI)."""
        return json.dumps(check_postgres(), indent=2)

    @app.tool()
    def check_mongodb_connection() -> str:
        """Verify migration target MongoDB (Atlas from .env, or local when no Atlas URI)."""
        return json.dumps(check_mongodb(), indent=2)

    @app.tool()
    def list_ddl_examples() -> str:
        """List bundled PostgreSQL DDL examples (simple learning sample + full e-commerce MVP)."""
        return json.dumps({"examples": list_examples()}, indent=2)

    @app.tool()
    def get_example_postgres_ddl(example_id: str = "simple_three_table") -> str:
        """Return bundled example DDL text and modeling notes without loading the session."""
        try:
            ex = get_example(example_id)
        except KeyError as err:
            return json.dumps({"error": str(err), "hint": "Call list_ddl_examples for valid ids."})
        ddl = ex.ddl_path.read_text(encoding="utf-8")
        discovery = (
            ex.discovery_path.read_text(encoding="utf-8") if ex.discovery_path and ex.discovery_path.is_file() else ""
        )
        return json.dumps(
            {
                "example_id": ex.id,
                "title": ex.title,
                "supports_deterministic_migration": ex.supports_deterministic_migration,
                "ddl": ddl,
                "discovery_snippet": discovery,
            },
            indent=2,
        )

    @app.tool()
    def load_ddl_example(example_id: str = "simple_three_table") -> str:
        """Load a bundled DDL example (and optional discovery snippet) into the session workspace."""
        result = _load_example_into_workspace(example_id)
        if "error" in result:
            return json.dumps(result, indent=2)
        result["next_steps"] = [
            "parse_postgres_ddl",
            "score_discovery_completeness (if transcript loaded)",
            "propose_target_schema_design",
        ]
        return json.dumps(result, indent=2)

    @app.tool()
    def load_simple_three_table_for_modeling() -> str:
        """One-shot: load simple_three_table DDL, parse inventory, score discovery, propose MongoDB schema.

        Prefer this over separate tool calls when the architect asks for the simple example for modeling.
        Returns all artifacts in one response (fewer LLM round-trips).
        """
        loaded = _load_example_into_workspace("simple_three_table")
        if "error" in loaded:
            return json.dumps(loaded, indent=2)
        inventory = _parse_ddl_in_workspace()
        if "error" in inventory:
            return json.dumps(inventory, indent=2)
        transcript = str(get_artifact("discovery_transcript", ""))
        discovery_score = score_transcript(transcript) if transcript.strip() else None
        if discovery_score:
            put_artifact("discovery_score", discovery_score)
        design = _propose_design_in_workspace()
        return json.dumps(
            {
                "status": "ready_for_review",
                "loaded": loaded,
                "source_inventory": inventory,
                "discovery_score": discovery_score,
                "target_schema_design": design,
                "note": "Design-only example; use ecommerce_mvp for migration execution.",
            },
            indent=2,
        )

    @app.tool()
    def load_bundled_demo_inputs() -> str:
        """Load the full 5-table e-commerce discovery transcript and DDL (same as load_ddl_example('ecommerce_mvp'))."""
        return load_ddl_example("ecommerce_mvp")

    @app.tool()
    def prepare_ecommerce_mvp_for_migration(include_row_counts: bool = True) -> str:
        """One-shot: load ecommerce_mvp, parse DDL, score discovery, propose schema, build migration plan.

        Use for the full 5-table PoC before HITL gates. Prefer over many separate tool calls.
        """
        loaded = _load_example_into_workspace("ecommerce_mvp")
        if "error" in loaded:
            return json.dumps(loaded, indent=2)
        inventory = _parse_ddl_in_workspace()
        if "error" in inventory:
            return json.dumps(inventory, indent=2)
        transcript = str(get_artifact("discovery_transcript", ""))
        discovery_score = score_transcript(transcript) if transcript.strip() else None
        if discovery_score:
            put_artifact("discovery_score", discovery_score)
        design = _propose_design_in_workspace()
        plan = _generate_plan_in_workspace()
        if "error" in plan:
            return json.dumps(
                {
                    "status": "partial",
                    "loaded": loaded,
                    "source_inventory": inventory,
                    "discovery_score": discovery_score,
                    "target_schema_design": design,
                    "migration_plan_error": plan,
                },
                indent=2,
            )
        if include_row_counts:
            try:
                inventory = _attach_row_counts(inventory)
            except Exception as exc:  # noqa: BLE001 — surface connection errors to the architect
                inventory = {**inventory, "row_counts_error": str(exc)}
        return json.dumps(
            {
                "status": "ready_for_hitl",
                "loaded": loaded,
                "source_inventory": inventory,
                "discovery_score": discovery_score,
                "target_schema_design": design,
                "migration_plan_summary": {
                    "version": plan.get("version"),
                    "target_database": plan.get("target", {}).get("database"),
                    "collections": [c.get("name") for c in plan.get("collections", [])],
                },
                "next_steps": [
                    "approve_discovery_completeness",
                    "approve_target_schema",
                    "approve_migration_execution",
                    "execute_migration_pipeline",
                    "run_validation_checks",
                ],
            },
            indent=2,
        )

    @app.tool()
    def parse_postgres_ddl(ddl_text: str = "") -> str:
        """Parse PostgreSQL DDL into a source inventory (tables, columns, references)."""
        if ddl_text.strip():
            put_artifact("ddl_text", ddl_text)
        inventory = _parse_ddl_in_workspace()
        if "error" in inventory:
            return json.dumps(inventory, indent=2)
        return json.dumps(inventory, indent=2)

    @app.tool()
    def build_source_inventory(include_row_counts: bool = True) -> str:
        """Enrich DDL inventory with optional live PostgreSQL row counts (POSTGRES_URI)."""
        inventory = get_artifact("source_inventory")
        if not inventory:
            return json.dumps({"error": "Run parse_postgres_ddl first."})
        if include_row_counts:
            try:
                inventory = _attach_row_counts(inventory)
            except Exception as exc:  # noqa: BLE001
                return json.dumps({"error": str(exc), "hint": "Check POSTGRES_URI and seed script."})
        return json.dumps(inventory, indent=2)

    @app.tool()
    def score_discovery_completeness(transcript: str = "") -> str:
        """Score discovery transcript against the 10-area playbook; gates PoC generation at 0.8."""
        text = resolve_discovery_transcript(transcript)
        if not text.strip():
            return json.dumps(
                {
                    "error": "No transcript.",
                    "hint": (
                        "Attach demo/playground-sample-payload.json in Playground (Extra arguments), "
                        "paste discovery text, or call load_bundled_demo_inputs."
                    ),
                }
            )
        result = score_transcript(text)
        put_artifact("discovery_score", result)
        return json.dumps(result, indent=2)

    @app.tool()
    def propose_target_schema_design() -> str:
        """Propose MongoDB collections, embedding decisions, and indexes for the in-scope workload."""
        example_id = str(get_artifact("ddl_example_id", "ecommerce_mvp"))
        if example_id == "simple_three_table":
            design = simple_three_table_schema_design()
        else:
            design = canonical_ecommerce_schema_design()
        put_artifact("target_schema_design", design)
        return json.dumps(design, indent=2)

    @app.tool()
    def generate_migration_plan() -> str:
        """Build migration-plan.json from inventory + design (deterministic for bundled demo)."""
        plan = _generate_plan_in_workspace()
        return json.dumps(plan, indent=2)

    @app.tool()
    def get_session_artifacts() -> str:
        """Return migration artifacts accumulated in this session (for Playground review)."""
        ws = workspace()
        keys = (
            "ddl_example_id",
            "discovery_score",
            "source_inventory",
            "ddl_risk_flags",
            "target_schema_design",
            "migration_plan",
            "migration_stats",
            "validation_report",
            "hitl_discovery",
            "hitl_schema",
            "hitl_execution",
        )
        return json.dumps({k: ws.get(k) for k in keys if k in ws}, indent=2)

    @app.tool()
    def execute_migration_pipeline() -> str:
        """Run the deterministic Postgres → MongoDB pipeline using migration-plan.json."""
        plan = get_artifact("migration_plan")
        if not plan:
            return json.dumps({"error": "No migration plan. Call generate_migration_plan after approvals."})
        hitl = get_artifact("hitl_execution") or {}
        if hitl.get("decision") != "approved":
            return json.dumps(
                {
                    "error": "Execution not authorized. Call approve_migration_execution first.",
                    "hitl_execution_seen": bool(hitl),
                }
            )
        try:
            stats = run_migration(plan)
        except Exception as exc:  # noqa: BLE001
            return json.dumps(
                {
                    "error": str(exc),
                    "hint": (
                        "Run check_postgres_connection and check_mongodb_connection; "
                        "Atlas URI belongs in .env as MONGODB_URI (or MIGRATION_TARGET_MONGODB_URI)."
                    ),
                },
                indent=2,
            )
        put_artifact("migration_stats", stats)
        return json.dumps({"status": "completed", "stats": stats}, indent=2)

    @app.tool()
    def run_validation_checks() -> str:
        """Run reconciliation checks (row counts, embedded line_items integrity)."""
        plan = get_artifact("migration_plan")
        if not plan:
            return json.dumps({"error": "No migration plan."})
        report = run_validation(plan)
        put_artifact("validation_report", report)
        return json.dumps(report, indent=2)

    @app.tool()
    def approve_discovery_completeness(
        summary: str,
        completeness_score: float,
        gaps: str = "",
    ) -> str:
        """HITL gate 1: architect confirms discovery extraction or records gaps."""
        answer = _await_hitl_approval(
            format_discovery_review_prompt(
                summary=summary,
                completeness_score=completeness_score,
                gaps=gaps,
            )
        )
        put_artifact("hitl_discovery", answer)
        return json.dumps(answer, indent=2)

    @app.tool()
    def approve_target_schema(
        schema_summary: str,
        embedding_rationale: str,
    ) -> str:
        """HITL gate 2: architect signs off on target document model and mapping."""
        answer = _await_hitl_approval(
            format_schema_review_prompt(
                schema_summary=schema_summary,
                embedding_rationale=embedding_rationale,
            )
        )
        put_artifact("hitl_schema", answer)
        if answer.get("decision") != "approved":
            return json.dumps({"status": "blocked", "detail": answer}, indent=2)
        return json.dumps({"status": "approved", "detail": answer}, indent=2)

    @app.tool()
    def approve_migration_execution(
        target_database: str = "",
        postgres_uri_hint: str = "",
        risk_summary: str = "",
    ) -> str:
        """HITL gate 3: authorize migration run against the configured Mongo target."""
        resolved_db = resolve_migration_target_db(target_database or "commerce_poc")
        uri_kind = mongodb_uri_kind(resolve_migration_mongodb_uri())
        hint = postgres_uri_hint.strip() or (
            "POSTGRES_URI configured for commerce_demo; use host.docker.internal:5433 from Docker"
        )
        answer = _await_hitl_approval(
            format_execution_review_prompt(
                target_database=resolved_db,
                postgres_uri_hint=hint,
                risk_summary=risk_summary
                or "Deterministic bulk load into MIGRATION_TARGET_DB; confirm Atlas/network access.",
                mongo_uri_kind=uri_kind,
            )
        )
        put_artifact("hitl_execution", answer)
        return json.dumps({**answer, "target_database": resolved_db, "target_uri_kind": uri_kind}, indent=2)
