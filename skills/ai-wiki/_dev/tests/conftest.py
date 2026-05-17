"""Shared fixtures for _dev harness tests."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

# Make `scripts/` importable for harness tests too.
_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))

CORPUS_DIR = Path(__file__).resolve().parent.parent / "corpus"


@pytest.fixture
def corpus() -> Path:
    """Path to the _dev/corpus/ directory."""
    return CORPUS_DIR


@pytest.fixture
def vault(tmp_path):
    """A clean vault rooted at a pytest tmp_path (mirrors scripts/tests/conftest.py)."""
    from vault import Vault
    return Vault(root=tmp_path / "ai-wiki")


@pytest.fixture
def seeded_vault(tmp_path, corpus: Path):
    """Vault pre-seeded with corpus source + concept + map."""
    from vault import Vault

    vault = Vault(root=tmp_path / "ai-wiki")

    src = corpus / "arxiv-sample.md"
    src_text = src.read_text(encoding="utf-8")
    (vault.root / "sources" / "arxiv-2604.14765.md").write_text(src_text, encoding="utf-8")

    shell = corpus / "concept-v1-shell.md"
    (vault.root / "concepts" / "vgf.md").write_text(shell.read_text(encoding="utf-8"), encoding="utf-8")

    enriched = corpus / "concept-v2-enriched.md"
    (vault.root / "concepts" / "wasserstein-gradient-flow.md").write_text(
        enriched.read_text(encoding="utf-8"), encoding="utf-8"
    )

    map_src = corpus / "map-sample.md"
    (vault.root / "maps" / "ai-root.md").write_text(map_src.read_text(encoding="utf-8"), encoding="utf-8")

    return vault


# Silence shutil import warning
_ = shutil  # noqa: F841
