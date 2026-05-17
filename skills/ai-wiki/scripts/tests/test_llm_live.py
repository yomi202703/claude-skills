"""Opt-in live integration tests for llm.py.

These tests actually invoke `claude -p` via subprocess. They are gated by
the `AI_WIKI_LLM_LIVE` environment variable so they do NOT run in default CI.

To run:
    AI_WIKI_LLM_LIVE=1 pytest scripts/tests/test_llm_live.py -v

Each test keeps prompts minimal to cap cost (~$0.01-0.05 per test on Haiku).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from llm import call_claude, call_with_template  # noqa: E402

LIVE = os.environ.get("AI_WIKI_LLM_LIVE") == "1"

pytestmark = pytest.mark.skipif(
    not LIVE,
    reason="live CLI test; set AI_WIKI_LLM_LIVE=1 to enable",
)


def test_live_haiku_minimal_roundtrip():
    """Smoke: claude CLI responds to a minimal prompt on Haiku."""
    r = call_claude("Reply with exactly: ACK", model="haiku")
    assert r.is_error is False, r.error_message
    assert "ACK" in r.text.upper()
    assert r.cost_usd > 0
    assert r.input_tokens > 0


def test_live_opus_json_output(tmp_path):
    """Opus returns parseable JSON when prompted for it."""
    prompt_path = tmp_path / "prompt.md"
    prompt_path.write_text(
        """# live_json_test v1.0

<!-- meta:
  model: opus
  parse_json: true
  -->

## User

Return a JSON object with 2 keys: `answer` (an integer), `why` (a string).

Question: 2 + 2 = ?
""",
        encoding="utf-8",
    )
    r = call_with_template(prompt_path, {})
    assert r.is_error is False
    assert r.parsed is not None
    assert isinstance(r.parsed, dict)
    assert r.parsed.get("answer") == 4


def test_live_error_propagation_bad_model():
    """Unknown model should produce an error (not a silent success)."""
    r = call_claude("hi", model="this-model-does-not-exist-xyz")
    # Either subprocess errors out or envelope marks error; assert at least
    # one of these signals
    assert r.is_error or r.text == ""
