#!/usr/bin/env python3
"""LLM boundary module (v4, REQUIREMENTS §13, SPEC §12).

Wraps the Claude Code CLI (`claude -p`) as a subprocess. The ONLY module
allowed to invoke LLMs. Other scripts call `call_claude()` from here.

Hard constraints (violating breaks Hard rule #4 and Path β philosophy):
- No `anthropic` SDK imports
- No direct HTTP calls to Claude API
- No auth credentials handled here (CC OAuth is used via the CLI)
- LLM outputs are returned as-is; callers are responsible for validation
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------- Model aliases ----------

MODEL_ALIASES = ("opus", "sonnet", "haiku")


# ---------- Result dataclass ----------


@dataclass
class CallResult:
    text: str                     # CLI's `result` field
    parsed: Any | None = None     # json.loads(text) if parse_json=True
    raw: dict = field(default_factory=dict)  # full CLI JSON envelope
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    duration_ms: int = 0
    is_error: bool = False
    error_message: str | None = None
    model_used: str = ""


# ---------- CLI invocation ----------


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


def _extract_json_block(text: str) -> Any | None:
    """Extract a JSON object/array from LLM text output.

    LLMs often wrap JSON in ```json ... ``` fences. Fall back to the first
    ``{`` / ``[`` to matching close. Returns None on parse failure.
    """
    stripped = text.strip()
    # Try direct parse first
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # Try ```json ... ``` fenced block
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", stripped, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass

    # Try first balanced {...} or [...]
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start = stripped.find(open_ch)
        if start < 0:
            continue
        depth = 0
        for i in range(start, len(stripped)):
            if stripped[i] == open_ch:
                depth += 1
            elif stripped[i] == close_ch:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(stripped[start:i + 1])
                    except json.JSONDecodeError:
                        break
    return None


def call_claude(
    prompt: str,
    *,
    model: str = "opus",
    system: str | None = None,
    parse_json: bool = False,
    timeout: int = 300,
) -> CallResult:
    """Invoke `claude -p` subprocess and return a structured result.

    Parameters
    ----------
    prompt
        User prompt, piped via stdin. Can be long (large documents).
    model
        "opus" / "sonnet" / "haiku" alias, or full model name.
    system
        Optional system prompt (passed via --system-prompt).
    parse_json
        If True, attempt json.loads on the `result` text (robust to code
        fences). Result stored in `parsed`. Failure leaves parsed=None.
    timeout
        Subprocess timeout in seconds. Default 300 (5 min).
    """
    if model in MODEL_ALIASES:
        cli_model = model
    else:
        cli_model = model  # full model name passes through

    args = _build_cli_args(cli_model, system)

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
            model_used=cli_model,
        )
    except FileNotFoundError:
        return CallResult(
            text="",
            is_error=True,
            error_message="`claude` CLI not found in PATH",
            model_used=cli_model,
        )

    if proc.returncode != 0:
        return CallResult(
            text="",
            is_error=True,
            error_message=f"non-zero exit ({proc.returncode}): {proc.stderr.strip()[:500]}",
            model_used=cli_model,
        )

    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        return CallResult(
            text=proc.stdout,
            is_error=True,
            error_message=f"CLI output not valid JSON: {e}",
            model_used=cli_model,
        )

    result_text = str(envelope.get("result", ""))
    is_error = bool(envelope.get("is_error", False))
    usage = envelope.get("usage", {}) or {}

    out = CallResult(
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
        model_used=cli_model,
    )

    if parse_json:
        out.parsed = _extract_json_block(result_text)

    return out


# ---------- Prompt template loader ----------

_META_RE = re.compile(r"<!--\s*meta:(.*?)-->", re.DOTALL)
_META_KV_RE = re.compile(r"^\s*([A-Za-z_][\w\-]*)\s*:\s*(.*?)\s*$", re.MULTILINE)
_SECTION_RE = re.compile(r"^##\s+(System|User)\s*$", re.MULTILINE)


@dataclass
class PromptTemplate:
    name: str
    version: str
    meta: dict
    system: str | None
    user: str

    def render(self, **placeholders: Any) -> tuple[str | None, str]:
        """Return (system_rendered, user_rendered) with placeholders filled."""
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
    """Load a prompt template file (see SPEC §12.6 format)."""
    path = Path(template_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / "prompts" / path
        if not path.suffix:
            path = path.with_suffix(".md")
    text = path.read_text(encoding="utf-8")

    # Parse header: `# <name> v<version>`
    header = re.match(r"^#\s+(\S+)\s+v([\d.]+)", text)
    if not header:
        raise ValueError(f"prompt template {path}: missing '# <name> v<version>' header")
    name = header.group(1)
    version = header.group(2)

    # Parse meta block
    meta_match = _META_RE.search(text)
    meta: dict = {}
    if meta_match:
        for kv in _META_KV_RE.finditer(meta_match.group(1)):
            val = kv.group(2).strip()
            if val.lower() in ("true", "false"):
                meta[kv.group(1)] = val.lower() == "true"
            else:
                meta[kv.group(1)] = val

    # Parse System / User sections
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
        meta=meta,
        system=sections.get("System"),
        user=sections["User"],
    )


# ---------- Convenience: template + call in one step ----------


def call_with_template(
    template: PromptTemplate | str | Path,
    placeholders: dict[str, Any],
    *,
    model: str | None = None,
    parse_json: bool | None = None,
    timeout: int = 300,
) -> CallResult:
    """Load template (if given as path), render, and call Claude."""
    tpl = template if isinstance(template, PromptTemplate) else load_prompt(template)
    system_text, user_text = tpl.render(**placeholders)
    effective_model = model or tpl.meta.get("model") or "opus"
    effective_parse = parse_json if parse_json is not None else bool(tpl.meta.get("parse_json", False))
    return call_claude(
        user_text,
        model=effective_model,
        system=system_text,
        parse_json=effective_parse,
        timeout=timeout,
    )


# ---------- Logging helper ----------


def log_call(vault_log_fn, op: str, slug: str | None, result: CallResult) -> None:
    """Append an llm_call line via vault.append_log.

    vault_log_fn: callable with signature (op: str, details: dict) -> None.
    Using injection keeps vault import out of this module's header for
    simpler testability; callers pass `vault.append_log`.
    """
    vault_log_fn(
        "llm_call",
        {
            "op": op,
            "slug": slug or "-",
            "model": result.model_used,
            "cost": f"{result.cost_usd:.4f}",
            "in": result.input_tokens,
            "out": result.output_tokens,
            "cache_read": result.cache_read_tokens,
            "error": "yes" if result.is_error else "no",
        },
    )
