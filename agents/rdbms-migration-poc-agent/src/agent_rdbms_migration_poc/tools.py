"""Migration PoC tools — deterministic execution, LLM-assisted orchestration."""

from __future__ import annotations

import json
import re
from typing import Any

import psycopg
from langgraph.types import interrupt
from magenta_sdklanggraph import App

from agent_rdbms_migration_poc.migration.ddl_parser import inventory_from_ddl
from agent_rdbms_migration_poc.migration.cross_check import cross_check_transcript_with_inventory
from agent_rdbms_migration_poc.migration.discovery import (
    execution_gate_error,
    plan_generation_gate_error,
    schema_approval_error,
    score_transcript,
)
from agent_rdbms_migration_poc.migration.examples import (
    get_example,
    list_examples,
    normalize_example_id,
    read_example_ddl,
    simple_three_table_schema_design,
)
from agent_rdbms_migration_poc.migration.intake import extract_structured_intake
from agent_rdbms_migration_poc.llm import build_llm
from agent_rdbms_migration_poc.migration.plan import (
    build_ecommerce_migration_plan,
    canonical_ecommerce_schema_design,
)
from agent_rdbms_migration_poc.migration.pipeline_architecture import build_pipeline_architecture
from agent_rdbms_migration_poc.migration.mongo_conn import check_mongodb
from agent_rdbms_migration_poc.migration.postgres_conn import check_postgres, resolve_postgres_uri
from agent_rdbms_migration_poc.poc_pack import format_poc_pack_catalog, format_poc_pack_review
from agent_rdbms_migration_poc.hitl import (
    format_discovery_review_prompt,
    format_execution_review_prompt,
    format_schema_review_prompt,
    normalize_hitl_answer,
)
from agent_rdbms_migration_poc.migration.runner import run_migration, run_validation
from agent_rdbms_migration_poc.workspace import (
    get_artifact,
    get_poc_pack,
    list_poc_packs,
    put_artifact,
    record_poc_artifact,
    resolve_discovery_transcript,
    workspace,
)

DEMO_TABLES = frozenset({"customers", "products", "orders", "order_items", "payments"})
_DISCOVERY_WAIVER_PATTERN = re.compile(r"\bapproved\s+with\s+(?:an?\s+)?waiver\b", re.IGNORECASE)


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
        risk_flags = {
            "missing_demo_tables": sorted(DEMO_TABLES - table_names),
            "unexpected_tables": sorted(table_names - DEMO_TABLES),
            "mvp_table_count_ok": DEMO_TABLES.issubset(table_names),
        }
        put_artifact("ddl_risk_flags", risk_flags)
        record_poc_artifact("source_inventory", {"inventory": inventory, "risk_flags": risk_flags})
        return inventory

    def _propose_design_in_workspace() -> dict[str, Any]:
        example_id = str(get_artifact("ddl_example_id", "ecommerce_mvp"))
        if example_id == "simple_three_table":
            design = simple_three_table_schema_design()
        else:
            design = canonical_ecommerce_schema_design()
        put_artifact("target_schema_design", design)
        record_poc_artifact("target_schema_design", design)
        return design

    def _generate_plan_in_workspace() -> dict[str, Any]:
        gate_error = plan_generation_gate_error(
            get_artifact("discovery_score"), get_artifact("hitl_discovery")
        )
        if gate_error:
            return gate_error
        schema_error = schema_approval_error(
            get_artifact("hitl_schema"), "generating a migration plan"
        )
        if schema_error:
            return schema_error
        inventory = get_artifact("source_inventory", {})
        table_names = {t["name"] for t in inventory.get("tables", [])}
        example_id = str(get_artifact("ddl_example_id", ""))
        if example_id == "simple_three_table":
            return {
                "error": "No migration-plan runner for simple_three_table (design-only example).",
                "hint": "Use ecommerce_mvp for execute_migration_pipeline.",
            }
        if DEMO_TABLES.issubset(table_names):
            try:
                plan = build_ecommerce_migration_plan(
                    inventory, get_artifact("target_schema_design", {})
                )
            except ValueError as err:
                return {"error": str(err)}
            put_artifact("migration_plan", plan)
            record_poc_artifact("field_mapping", plan["field_mappings"])
            record_poc_artifact("migration_plan", plan)
            architecture = build_pipeline_architecture(plan)
            put_artifact("pipeline_architecture", architecture)
            record_poc_artifact("pipeline_architecture", architecture)
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
        record_poc_artifact("source_inventory_row_counts", enriched)
        return enriched

    def _score_discovery_in_workspace(transcript: str) -> dict[str, Any]:
        result = score_transcript(transcript)
        put_artifact("discovery_score", result)
        record_poc_artifact("discovery_assessment", result)
        return result

    def _cross_check_in_workspace(transcript: str) -> dict[str, Any]:
        inventory = get_artifact("source_inventory")
        if not inventory:
            return {"error": "No source inventory. Run parse_postgres_ddl first."}
        result = cross_check_transcript_with_inventory(transcript, inventory)
        put_artifact("discovery_schema_cross_check", result)
        record_poc_artifact("discovery_schema_cross_check", result)
        return result

    def _extract_intake_in_workspace(transcript: str, use_llm: bool) -> dict[str, Any]:
        invoke_llm = None
        if use_llm:
            try:
                invoke_llm = build_llm(temperature=0).invoke
            except Exception:  # noqa: BLE001 - deterministic extraction is always available
                pass
        intake = extract_structured_intake(transcript, invoke_llm)
        put_artifact("structured_discovery_intake", intake)
        record_poc_artifact("structured_discovery_intake", intake)
        return intake

    @app.tool()
    def check_postgres_connection() -> str:
        """Verify demo Postgres is reachable from this runtime (POSTGRES_URI)."""
        return json.dumps(check_postgres(), indent=2)

    @app.tool()
    def check_mongodb_connection() -> str:
        """Verify MongoDB target is reachable with MONGODB_URI."""
        return json.dumps(check_mongodb(get_artifact("migration_plan")), indent=2)

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
        discovery_score = _score_discovery_in_workspace(transcript) if transcript.strip() else None
        intake = _extract_intake_in_workspace(transcript, use_llm=False) if transcript.strip() else None
        cross_check = _cross_check_in_workspace(transcript) if transcript.strip() else None
        design = _propose_design_in_workspace()
        return json.dumps(
            {
                "status": "ready_for_review",
                "loaded": loaded,
                "source_inventory": inventory,
                "discovery_score": discovery_score,
                "structured_discovery_intake": intake,
                "discovery_schema_cross_check": cross_check,
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
        """One-shot: load ecommerce_mvp, parse DDL, score discovery, and propose schema.

        Use for the full 5-table PoC before HITL gates. Prefer over many separate tool calls.
        """
        loaded = _load_example_into_workspace("ecommerce_mvp")
        if "error" in loaded:
            return json.dumps(loaded, indent=2)
        inventory = _parse_ddl_in_workspace()
        if "error" in inventory:
            return json.dumps(inventory, indent=2)
        transcript = str(get_artifact("discovery_transcript", ""))
        discovery_score = _score_discovery_in_workspace(transcript) if transcript.strip() else None
        intake = _extract_intake_in_workspace(transcript, use_llm=False) if transcript.strip() else None
        cross_check = _cross_check_in_workspace(transcript) if transcript.strip() else None
        design = _propose_design_in_workspace()
        if include_row_counts:
            try:
                inventory = _attach_row_counts(inventory)
            except Exception as exc:  # noqa: BLE001 — surface connection errors to the architect
                inventory = {**inventory, "row_counts_error": str(exc)}
        return json.dumps(
            {
                "status": "ready_for_discovery_review",
                "loaded": loaded,
                "source_inventory": inventory,
                "discovery_score": discovery_score,
                "structured_discovery_intake": intake,
                "discovery_schema_cross_check": cross_check,
                "target_schema_design": design,
                "next_steps": [
                    "approve_discovery_completeness",
                    "approve_target_schema",
                    "generate_migration_plan",
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
        result = _score_discovery_in_workspace(text)
        return json.dumps(result, indent=2)

    @app.tool()
    def cross_check_discovery_with_source(transcript: str = "") -> str:
        """Compare discovery entities and relationship claims with the parsed source DDL inventory."""
        text = resolve_discovery_transcript(transcript)
        if not text.strip():
            return json.dumps({"error": "No transcript. Call score_discovery_completeness first."})
        return json.dumps(_cross_check_in_workspace(text), indent=2)

    @app.tool()
    def extract_structured_discovery_intake(transcript: str = "") -> str:
        """Extract evidence-linked discovery facts with the LLM, or deterministic fallback if unavailable."""
        text = resolve_discovery_transcript(transcript)
        if not text.strip():
            return json.dumps({"error": "No transcript. Attach or load a discovery transcript first."})
        return json.dumps(_extract_intake_in_workspace(text, use_llm=True), indent=2)

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
    def generate_pipeline_architecture() -> str:
        """Describe the deterministic extract-transform-load-validate architecture for the migration plan."""
        plan = get_artifact("migration_plan")
        if not plan:
            return json.dumps({"error": "No migration plan. Generate and approve the plan first."})
        architecture = build_pipeline_architecture(plan)
        put_artifact("pipeline_architecture", architecture)
        record_poc_artifact("pipeline_architecture", architecture)
        return json.dumps(architecture, indent=2)

    @app.tool()
    def get_session_artifacts() -> str:
        """Return migration artifacts accumulated in this session (for Playground review)."""
        ws = workspace()
        keys = (
            "ddl_example_id",
            "discovery_score",
            "structured_discovery_intake",
            "source_inventory",
            "ddl_risk_flags",
            "discovery_schema_cross_check",
            "target_schema_design",
            "migration_plan",
            "pipeline_architecture",
            "migration_stats",
            "validation_report",
            "hitl_discovery",
            "hitl_schema",
            "hitl_execution",
        )
        return json.dumps({k: ws.get(k) for k in keys if k in ws}, indent=2)

    @app.tool()
    def get_poc_pack_artifacts(session_id: str = "") -> str:
        """Return immutable discovery-to-validation artifacts for this or a selected session."""
        return json.dumps({"artifacts": get_poc_pack(session_id)}, indent=2)

    @app.tool()
    def list_persisted_poc_packs() -> str:
        """List recent persisted PoC packs so an architect can review or reuse a prior session."""
        return json.dumps({"packs": list_poc_packs()}, indent=2)

    @app.tool()
    def get_poc_pack_review(session_id: str = "") -> str:
        """Render this or a selected persisted session as a concise Markdown PoC-pack review."""
        records = get_poc_pack(session_id)
        review = format_poc_pack_review(records)
        if records:
            return review
        return f"{review}\n\n{format_poc_pack_catalog(list_poc_packs())}"

    @app.tool()
    def execute_migration_pipeline() -> str:
        """Run the deterministic Postgres → MongoDB pipeline using migration-plan.json."""
        plan = get_artifact("migration_plan")
        if not plan:
            return json.dumps({"error": "No migration plan. Call generate_migration_plan after approvals."})
        gate_error = execution_gate_error(
            get_artifact("discovery_score"),
            get_artifact("hitl_discovery"),
            get_artifact("hitl_schema"),
        )
        if gate_error:
            return json.dumps(gate_error, indent=2)
        hitl = get_artifact("hitl_execution") or {}
        if hitl.get("decision") != "approved":
            return json.dumps(
                {
                    "error": "Execution not authorized. Call approve_migration_execution first.",
                    "hitl_execution_seen": bool(hitl),
                }
            )
        mongo_preflight = check_mongodb(plan)
        if not mongo_preflight["ok"]:
            return json.dumps(mongo_preflight, indent=2)
        try:
            stats = run_migration(plan)
        except Exception as exc:  # noqa: BLE001
            return json.dumps(
                {
                    "error": str(exc),
                    "hint": "Run check_postgres_connection; ensure MONGODB_URI is set in dev.",
                },
                indent=2,
            )
        put_artifact("migration_stats", stats)
        record_poc_artifact("migration_execution", stats)
        return json.dumps({"status": "completed", "stats": stats}, indent=2)

    @app.tool()
    def run_validation_checks() -> str:
        """Run reconciliation checks (row counts, embedded line_items integrity)."""
        plan = get_artifact("migration_plan")
        if not plan:
            return json.dumps({"error": "No migration plan."})
        report = run_validation(plan)
        put_artifact("validation_report", report)
        record_poc_artifact("validation_report", report)
        return json.dumps(report, indent=2)

    @app.tool()
    def approve_discovery_completeness(
        summary: str,
        completeness_score: float,
        gaps: str = "",
    ) -> str:
        """HITL gate 1: architect confirms discovery extraction or explicitly waives gaps."""
        answer = _await_hitl_approval(
            format_discovery_review_prompt(
                summary=summary,
                completeness_score=completeness_score,
                gaps=gaps,
            )
        )
        answer["waives_incomplete_discovery"] = bool(
            answer.get("decision") == "approved"
            and _DISCOVERY_WAIVER_PATTERN.search(answer.get("reviewer_notes", ""))
        )
        put_artifact("hitl_discovery", answer)
        record_poc_artifact("hitl_discovery", answer)
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
        record_poc_artifact("hitl_schema", answer)
        if answer.get("decision") != "approved":
            return json.dumps({"status": "blocked", "detail": answer}, indent=2)
        return json.dumps({"status": "approved", "detail": answer}, indent=2)

    @app.tool()
    def approve_migration_execution(
        target_database: str,
        postgres_uri_hint: str,
        risk_summary: str,
    ) -> str:
        """HITL gate 3: authorize migration run against Atlas."""
        answer = _await_hitl_approval(
            format_execution_review_prompt(
                target_database=target_database,
                postgres_uri_hint=postgres_uri_hint,
                risk_summary=risk_summary,
            )
        )
        put_artifact("hitl_execution", answer)
        record_poc_artifact("hitl_execution", answer)
        return json.dumps(answer, indent=2)
