"""Tests for llm.py (offline, subprocess mocked)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from llm import (  # noqa: E402
    CallResult,
    _extract_json_block,
    _replace_placeholders,
    call_claude,
    call_with_template,
    load_prompt,
    log_call,
)

# ---------- _extract_json_block ----------


def test_extract_json_direct():
    assert _extract_json_block('{"a": 1}') == {"a": 1}


def test_extract_json_fenced():
    text = 'Here is JSON:\n```json\n{"a": 2}\n```\nEnd.'
    assert _extract_json_block(text) == {"a": 2}


def test_extract_json_embedded():
    text = 'prose prose {"key": "value"} more prose'
    assert _extract_json_block(text) == {"key": "value"}


def test_extract_json_array():
    text = 'result:\n[1, 2, 3]\n'
    assert _extract_json_block(text) == [1, 2, 3]


def test_extract_json_invalid_returns_none():
    assert _extract_json_block("not json at all") is None


def test_extract_json_nested_braces():
    text = '{"outer": {"inner": [1, 2]}}'
    assert _extract_json_block(text) == {"outer": {"inner": [1, 2]}}


# ---------- _replace_placeholders ----------


def test_replace_placeholders_basic():
    out = _replace_placeholders("Hello {{name}}!", {"name": "World"})
    assert out == "Hello World!"


def test_replace_placeholders_multiple():
    out = _replace_placeholders("{{a}} + {{b}} = {{c}}", {"a": 1, "b": 2, "c": 3})
    assert out == "1 + 2 = 3"


def test_replace_placeholders_missing_raises():
    with pytest.raises(KeyError):
        _replace_placeholders("{{missing}}", {})


# ---------- call_claude (subprocess mocked) ----------


def _mock_cli_success(stdout_json: dict):
    """Factory: returns a fake subprocess.run result."""
    class Fake:
        def __init__(self):
            self.returncode = 0
            self.stdout = json.dumps(stdout_json)
            self.stderr = ""
    return Fake()


def test_call_claude_success(monkeypatch):
    envelope = {
        "type": "result",
        "result": "4",
        "is_error": False,
        "duration_ms": 1000,
        "total_cost_usd": 0.01,
        "usage": {
            "input_tokens": 10,
            "output_tokens": 5,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        },
    }
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: _mock_cli_success(envelope)
    )
    r = call_claude("What is 2+2?")
    assert r.is_error is False
    assert r.text == "4"
    assert r.cost_usd == 0.01
    assert r.input_tokens == 10
    assert r.output_tokens == 5


def test_call_claude_non_zero_exit(monkeypatch):
    class Fake:
        returncode = 1
        stdout = ""
        stderr = "boom"
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: Fake())
    r = call_claude("hello")
    assert r.is_error is True
    assert "boom" in (r.error_message or "")


def test_call_claude_cli_not_found(monkeypatch):
    def raise_fnf(*a, **k):
        raise FileNotFoundError()
    monkeypatch.setattr(subprocess, "run", raise_fnf)
    r = call_claude("hello")
    assert r.is_error is True
    assert "claude" in (r.error_message or "").lower()


def test_call_claude_timeout(monkeypatch):
    def raise_timeout(*a, **k):
        raise subprocess.TimeoutExpired(cmd="claude", timeout=1)
    monkeypatch.setattr(subprocess, "run", raise_timeout)
    r = call_claude("hello", timeout=1)
    assert r.is_error is True
    assert "timeout" in (r.error_message or "").lower()


def test_call_claude_invalid_stdout_json(monkeypatch):
    class Fake:
        returncode = 0
        stdout = "not json"
        stderr = ""
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: Fake())
    r = call_claude("hello")
    assert r.is_error is True


def test_call_claude_parse_json(monkeypatch):
    envelope = {
        "result": '{"items": [1, 2, 3]}',
        "is_error": False,
        "duration_ms": 100,
        "total_cost_usd": 0.01,
        "usage": {},
    }
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _mock_cli_success(envelope))
    r = call_claude("give me items", parse_json=True)
    assert r.parsed == {"items": [1, 2, 3]}


def test_call_claude_builds_correct_args(monkeypatch):
    recorded: dict = {}

    def capture(args, input=None, **kwargs):  # noqa: A002 shadow
        recorded["args"] = args
        recorded["input"] = input

        class Fake:
            returncode = 0
            stdout = json.dumps({"result": "ok", "usage": {}, "total_cost_usd": 0.0})
            stderr = ""
        return Fake()

    monkeypatch.setattr(subprocess, "run", capture)
    call_claude("Hello", model="sonnet", system="You are Socrates.")
    assert recorded["args"][:2] == ["claude", "-p"]
    assert "--model" in recorded["args"]
    assert "sonnet" in recorded["args"]
    assert "--system-prompt" in recorded["args"]
    assert "--no-session-persistence" in recorded["args"]
    assert recorded["input"] == "Hello"


# ---------- Prompt template ----------


@pytest.fixture
def tmp_prompt(tmp_path) -> Path:
    p = tmp_path / "greet.md"
    p.write_text(
        """# greet v1.0

<!-- meta:
  model: opus
  parse_json: false
  -->

## System

You are a friendly greeter.

## User

Say hi to {{name}}.
""",
        encoding="utf-8",
    )
    return p


def test_load_prompt_parses_header_and_sections(tmp_prompt: Path):
    tpl = load_prompt(tmp_prompt)
    assert tpl.name == "greet"
    assert tpl.version == "1.0"
    assert tpl.meta["model"] == "opus"
    assert tpl.meta["parse_json"] is False
    assert tpl.system is not None and "friendly" in tpl.system
    assert "{{name}}" in tpl.user


def test_load_prompt_render_substitutes(tmp_prompt: Path):
    tpl = load_prompt(tmp_prompt)
    system, user = tpl.render(name="Alice")
    assert "friendly" in system  # type: ignore[operator]
    assert "Say hi to Alice." in user


def test_load_prompt_missing_header_raises(tmp_path: Path):
    p = tmp_path / "bad.md"
    p.write_text("## User\nhello\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_prompt(p)


def test_load_prompt_missing_user_section_raises(tmp_path: Path):
    p = tmp_path / "bad.md"
    p.write_text("# foo v1.0\n## System\nonly system\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_prompt(p)


def test_call_with_template_uses_meta_model(tmp_prompt: Path, monkeypatch):
    tpl = load_prompt(tmp_prompt)
    recorded: dict = {}

    def capture(args, input=None, **kwargs):  # noqa: A002
        recorded["args"] = args

        class Fake:
            returncode = 0
            stdout = json.dumps({"result": "hi Alice", "usage": {}, "total_cost_usd": 0.0})
            stderr = ""
        return Fake()

    monkeypatch.setattr(subprocess, "run", capture)
    r = call_with_template(tpl, {"name": "Alice"})
    assert r.text == "hi Alice"
    assert "opus" in recorded["args"]


# ---------- log_call ----------


def test_log_call_emits_expected_fields():
    calls: list[tuple[str, dict]] = []

    def fake_log(op: str, details: dict) -> None:
        calls.append((op, details))

    r = CallResult(
        text="ok",
        cost_usd=0.05,
        input_tokens=100,
        output_tokens=50,
        cache_read_tokens=200,
        model_used="opus",
        is_error=False,
    )
    log_call(fake_log, "test_op", "my-slug", r)
    assert len(calls) == 1
    op, details = calls[0]
    assert op == "llm_call"
    assert details["op"] == "test_op"
    assert details["slug"] == "my-slug"
    assert details["model"] == "opus"
    assert details["in"] == 100
    assert details["out"] == 50
    assert details["error"] == "no"


def test_log_call_marks_error():
    calls: list[tuple[str, dict]] = []

    def fake_log(op: str, details: dict) -> None:
        calls.append((op, details))

    r = CallResult(text="", is_error=True, error_message="boom")
    log_call(fake_log, "x", None, r)
    assert calls[0][1]["error"] == "yes"
    assert calls[0][1]["slug"] == "-"
