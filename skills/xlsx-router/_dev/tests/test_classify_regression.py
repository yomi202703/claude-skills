"""Golden-baseline regression tests for xlsx_classify.py.

Run: `pytest ~/.claude/skills/xlsx/_dev/tests/ -q`

On first run (or after intentional classify output changes), delete the
corresponding <basename>.yml under tests/test_classify_regression/ and
re-run — pytest-regressions will write new baselines and fail once so
you can inspect + commit them.
"""
import json
import re
import subprocess
from pathlib import Path

import pytest

SKILL_DIR = Path.home() / ".claude/skills/xlsx"
CORPUS = SKILL_DIR / "_dev/corpus"
CLASSIFY = SKILL_DIR / "scripts/xlsx_classify.py"

CORPUS_FILES = sorted(CORPUS.glob("*.xlsx"))


def _safe_basename(path: Path) -> str:
    """ASCII-safe basename for the golden file; keeps readability where possible."""
    stem = path.stem
    stem = re.sub(r"[【】（）・]", "_", stem)
    stem = re.sub(r"_+", "_", stem).strip("_")
    return stem


def _classify(xlsx_path: Path) -> dict:
    result = subprocess.run(
        ["python3", str(CLASSIFY), str(xlsx_path)],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    data = json.loads(result.stdout)
    # Strip machine-specific absolute path; the filename alone is portable.
    data["file"] = Path(data["file"]).name
    return data


@pytest.mark.parametrize(
    "xlsx",
    CORPUS_FILES,
    ids=lambda p: p.stem,
)
def test_classify_matches_baseline(xlsx: Path, data_regression):
    result = _classify(xlsx)
    data_regression.check(result, basename=_safe_basename(xlsx))
