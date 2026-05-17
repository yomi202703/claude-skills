"""Shared pytest fixtures for ai-wiki tests."""
from __future__ import annotations

import sys
from pathlib import Path

# Make `scripts/` importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from vault import Vault  # noqa: E402


@pytest.fixture
def vault(tmp_path) -> Vault:
    """A clean vault rooted at a pytest tmp_path."""
    return Vault(root=tmp_path / "ai-wiki")
