"""Human-in-the-loop answer normalization (plain text or structured)."""

from __future__ import annotations

import json
import re
from typing import Any

# Playground renders a single text field when the interrupt uses a string schema.
NATURAL_LANGUAGE_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "string",
    "description": (
        "Approve or reject in plain language, e.g. "
        "'Approved — proceed to schema design' or 'Rejected — need Postgres row counts first'."
    ),
}

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
