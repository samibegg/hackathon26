"""Filesystem paths for bundled demo assets (per-agent demo/ directory)."""

from __future__ import annotations

import os
from pathlib import Path


def agent_root() -> Path:
    """Agent project root (contains demo/, agent.yaml). Set via MIGRATION_AGENT_ROOT in main."""
    override = os.environ.get("MIGRATION_AGENT_ROOT", "").strip()
    if override:
        return Path(override)
    return Path.cwd()
