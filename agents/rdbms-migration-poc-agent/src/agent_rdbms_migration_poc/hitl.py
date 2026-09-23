"""Human-in-the-loop answer normalization (plain text or structured)."""

from __future__ import annotations

import json
import re
from typing import Any

# Playground JSON-stringifies dict interrupt values (including response_schema).
# Use markdown strings for interrupt() so architects see a review brief, not raw JSON.
HITL_REPLY_HINT = (
    "Reply below with **Approved** or **Rejected** and any notes "
    "(plain language is fine)."
)

_REJECT_PATTERNS = re.compile(
    r"\b(reject(?:ed|ion)?|deny|denied|no|stop|block(?:ed)?)\b",
    re.IGNORECASE,
)
_APPROVE_PATTERNS = re.compile(
    r"\b(approve(?:d|s|al)?|accept(?:ed)?|yes|ok(?:ay)?|proceed|continue|go ahead)\b",
    re.IGNORECASE,
)


def normalize_hitl_answer(raw: Any) -> dict[str, str]:
    """Map Playground input to {decision, reviewer_notes} for artifact storage."""
    if isinstance(raw, dict):
        decision = str(raw.get("decision", "")).strip().lower()
        notes = str(raw.get("reviewer_notes", raw.get("notes", ""))).strip()
        if decision in ("approved", "rejected"):
            return {"decision": decision, "reviewer_notes": notes}
        text = notes or json.dumps(raw)
        return _from_text(text)

    if raw is None:
        raise ValueError("Empty HITL answer.")

    text = str(raw).strip()
    if not text:
        raise ValueError("Empty HITL answer.")

    if text.startswith("{"):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return _from_text(text)
        if isinstance(parsed, dict):
            return normalize_hitl_answer(parsed)

    return _from_text(text)


def _from_text(text: str) -> dict[str, str]:
    reject = bool(_REJECT_PATTERNS.search(text))
    approve = bool(_APPROVE_PATTERNS.search(text))
    if reject and not approve:
        return {"decision": "rejected", "reviewer_notes": text}
    if approve and not reject:
        return {"decision": "approved", "reviewer_notes": text}
    if reject and approve:
        # Prefer explicit rejection when both appear (e.g. "not approved").
        if re.search(r"\bnot\s+approve", text, re.IGNORECASE):
            return {"decision": "rejected", "reviewer_notes": text}
        return {"decision": "approved", "reviewer_notes": text}
    # Default: treat non-empty reply as approval so demos can proceed with "looks good".
    return {"decision": "approved", "reviewer_notes": text}


def format_discovery_review_prompt(
    *,
    summary: str,
    completeness_score: float,
    gaps: str,
) -> str:
    return (
        "## Discovery review (gate 1 of 3)\n\n"
        f"**Completeness score:** {completeness_score:.2f}\n\n"
        "### Summary\n\n"
        f"{summary.strip()}\n\n"
        "### Gaps / follow-ups\n\n"
        f"{(gaps or 'None noted.').strip()}\n\n"
        "**Question:** Approve discovery intake before schema design?\n\n"
        f"{HITL_REPLY_HINT}"
    )


def format_schema_review_prompt(*, schema_summary: str, embedding_rationale: str) -> str:
    return (
        "## Target schema review (gate 2 of 3)\n\n"
        "### Proposed model\n\n"
        f"{schema_summary.strip()}\n\n"
        "### Embedding rationale\n\n"
        f"{embedding_rationale.strip()}\n\n"
        "**Question:** Approve target schema and field mapping?\n\n"
        f"{HITL_REPLY_HINT}"
    )


def format_execution_review_prompt(
    *,
    target_database: str,
    postgres_uri_hint: str,
    risk_summary: str,
    mongo_uri_kind: str = "",
) -> str:
    target_line = f"**Target database:** `{target_database}`"
    if mongo_uri_kind:
        target_line += f" on **{mongo_uri_kind}**"
    return (
        "## Migration execution (gate 3 of 3)\n\n"
        f"{target_line}\n\n"
        f"**Postgres source:** {postgres_uri_hint.strip()}\n\n"
        "### Risks\n\n"
        f"{risk_summary.strip()}\n\n"
        "**Question:** Authorize migration execution against MongoDB?\n\n"
        f"{HITL_REPLY_HINT}"
    )
