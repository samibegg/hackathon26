"""Filesystem paths for bundled demo assets."""

from __future__ import annotations

from pathlib import Path


def agent_root() -> Path:
    """Agent project root (contains demo/, src/, pyproject.toml)."""
    return Path(__file__).resolve().parents[2]
