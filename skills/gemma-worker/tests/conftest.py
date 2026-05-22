from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKER_LLM_BASE_URL", "https://mock.invalid/v1")
    monkeypatch.setenv("WORKER_LLM_API_KEY", "sk-test")
    monkeypatch.setenv("WORKER_LLM_MODEL", "gemma-test")
    monkeypatch.setenv("WORKER_LLM_PROVIDER", "gemma")


@pytest.fixture
def live_env_present() -> bool:
    required = ("WORKER_LLM_BASE_URL", "WORKER_LLM_API_KEY", "WORKER_LLM_MODEL")
    return all(os.environ.get(k) for k in required)


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    return tmp_path / "test_store.db"
