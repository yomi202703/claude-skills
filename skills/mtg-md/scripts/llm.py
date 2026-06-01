#!/usr/bin/env python3
"""LLM boundary for convo-md.

Single subprocess gateway to `claude -p`. Mirrors pdf-to-md/llm.py but
trimmed: convo-md only invokes one prompt template (compress_chunk) per
chunk, no inner-Read needed (we pass the chunk text inline), so Read tool
is not required.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CallResult:
    text: str
    raw: dict = field(default_factory=dict)
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    duration_ms: int = 0
    is_error: bool = False
    error_message: str | None = None
    model_used: str = ""


def _build_cli_args(model: str, system: str | None) -> list[str]:
    args = [
        "claude",
        "-p",
        "--model", model,
        "--output-format", "json",
        "--no-session-persistence",
    ]
    if system:
        args.extend(["--system-prompt", system])
    return args


def call_claude(
    prompt: str,
    *,
    model: str = "claude-haiku-4-5-20251001",
    system: str | None = None,
    timeout: int = 600,
) -> CallResult:
    args = _build_cli_args(model, system)

    try:
        proc = subprocess.run(
            args,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        return CallResult(
            text="",
            is_error=True,
            error_message=f"subprocess timeout after {e.timeout}s",
            model_used=model,
        )
    except FileNotFoundError:
        return CallResult(
            text="",
            is_error=True,
            error_message="`claude` CLI not found in PATH",
            model_used=model,
        )

    if proc.returncode != 0:
        return CallResult(
            text="",
            is_error=True,
            error_message=f"non-zero exit ({proc.returncode}): {proc.stderr.strip()[:500]}",
            model_used=model,
        )

    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        return CallResult(
            text=proc.stdout,
            is_error=True,
            error_message=f"CLI output not valid JSON: {e}",
            model_used=model,
        )

    result_text = str(envelope.get("result", ""))
    is_error = bool(envelope.get("is_error", False))
    usage = envelope.get("usage", {}) or {}

    return CallResult(
        text=result_text,
        raw=envelope,
        cost_usd=float(envelope.get("total_cost_usd", 0.0) or 0.0),
        input_tokens=int(usage.get("input_tokens", 0) or 0),
        output_tokens=int(usage.get("output_tokens", 0) or 0),
        cache_read_tokens=int(usage.get("cache_read_input_tokens", 0) or 0),
        cache_creation_tokens=int(usage.get("cache_creation_input_tokens", 0) or 0),
        duration_ms=int(envelope.get("duration_ms", 0) or 0),
        is_error=is_error,
        error_message=str(envelope.get("api_error_status") or "") if is_error else None,
        model_used=model,
    )


# ---------- Prompt template loader (System / User sections) ----------

_SECTION_RE = re.compile(r"^##\s+(System|User)\s*$", re.MULTILINE)


@dataclass
class PromptTemplate:
    name: str
    version: str
    system: str | None
    user: str

    def render(self, **placeholders: Any) -> tuple[str | None, str]:
        sys_out = _replace_placeholders(self.system, placeholders) if self.system else None
        user_out = _replace_placeholders(self.user, placeholders)
        return sys_out, user_out


def _replace_placeholders(text: str, placeholders: dict[str, Any]) -> str:
    def sub(m: re.Match) -> str:
        key = m.group(1).strip()
        if key not in placeholders:
            raise KeyError(f"placeholder {{{{{key}}}}} not provided")
        return str(placeholders[key])
    return re.sub(r"\{\{\s*([A-Za-z_][\w\-]*)\s*\}\}", sub, text)


def load_prompt(template_path: Path | str) -> PromptTemplate:
    path = Path(template_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / "prompts" / path
        if not path.suffix:
            path = path.with_suffix(".md")
    text = path.read_text(encoding="utf-8")

    header = re.match(r"^#\s+(\S+)\s+v([\d.]+)", text)
    if not header:
        raise ValueError(f"prompt template {path}: missing '# <name> v<version>' header")
    name = header.group(1)
    version = header.group(2)

    sections: dict[str, str] = {}
    boundaries = [(m.start(), m.group(1)) for m in _SECTION_RE.finditer(text)]
    if not boundaries:
        raise ValueError(f"prompt template {path}: no '## System' or '## User' section found")
    for i, (start, label) in enumerate(boundaries):
        body_start = text.find("\n", start) + 1
        body_end = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(text)
        sections[label] = text[body_start:body_end].strip()
    if "User" not in sections:
        raise ValueError(f"prompt template {path}: '## User' section is required")
    return PromptTemplate(
        name=name,
        version=version,
        system=sections.get("System"),
        user=sections["User"],
    )


def call_with_template(
    template_path: Path | str,
    placeholders: dict[str, Any],
    *,
    model: str = "claude-haiku-4-5-20251001",
    timeout: int = 600,
) -> CallResult:
    tpl = load_prompt(template_path)
    system_text, user_text = tpl.render(**placeholders)
    return call_claude(
        user_text,
        model=model,
        system=system_text,
        timeout=timeout,
    )
