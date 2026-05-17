#!/usr/bin/env python3
"""Stage 1: deterministic JSONL → cleaned md.

Improved successor to /tmp/convert_log.py. Strips:
- thinking / tool_use / tool_result blocks (text only)
- Pure system-reminder / <command-...> messages
- Trailing Downloads link bullets
- Completion-report boilerplate
- Pasted skill spec user messages
- Trailing Sources: citation blocks
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable


# Single-line completion-report boilerplate. Matched against a stripped line.
COMPLETION_LINES = frozenset({
    "反映完了。",
    "反映完了",
    "完了しました。",
    "完了しました",
    "Now generate PDF:",
    "Now generate PDF",
    "PDF・MD ともに Downloads に反映済みです。",
    "完璧に反映されました。",
    "pptx 出力完了。",
    "pptx 出力完了",
    "PDF を再生成しました。",
})

# Downloads link line pattern.
_DOWNLOADS_LINK_RE = re.compile(
    r"^\s*-\s*\[[^\]]+\]\((?:file:)?/Users/[^/]+/Downloads/[^)]+\)\s*$"
)

# Sources block header.
_SOURCES_HEADER_RE = re.compile(r"^\s*Sources:\s*$")

# Bullet-link line under Sources.
_BULLET_LINK_RE = re.compile(r"^\s*-\s*\[[^\]]+\]\([^)]+\)\s*$")

# Pasted skill spec marker (user message).
_SKILL_SPEC_MARKER = "Base directory for this skill:"


def _clean_text_block(text: str) -> str:
    """Apply line-level filters to a single message's text block."""
    lines = text.splitlines()
    out: list[str] = []
    in_sources = False

    for raw in lines:
        stripped = raw.strip()

        # Sources block: drop header and following bullet-link lines until a non-bullet appears.
        if _SOURCES_HEADER_RE.match(raw):
            in_sources = True
            continue
        if in_sources:
            if _BULLET_LINK_RE.match(raw) or stripped == "":
                continue
            in_sources = False  # fall through to normal handling

        # Downloads link bullet lines — drop.
        if _DOWNLOADS_LINK_RE.match(raw):
            continue

        # Completion-report boilerplate — drop only when it stands alone on the line.
        if stripped in COMPLETION_LINES:
            continue

        out.append(raw)

    # Collapse triple+ blank lines to one.
    collapsed: list[str] = []
    blank_run = 0
    for line in out:
        if line.strip() == "":
            blank_run += 1
            if blank_run <= 1:
                collapsed.append("")
        else:
            blank_run = 0
            collapsed.append(line)

    # Trim trailing blanks.
    while collapsed and collapsed[-1].strip() == "":
        collapsed.pop()

    return "\n".join(collapsed).strip()


def _is_pasted_skill_spec(text: str) -> bool:
    """User message that's almost entirely a pasted skill specification."""
    if _SKILL_SPEC_MARKER not in text:
        return False
    # Heuristic: if the marker appears in the first 200 chars and the message is long, treat as spec paste.
    return text.find(_SKILL_SPEC_MARKER) < 500 and len(text) > 1500


def _extract_text_from_content(content) -> str:
    """Pull text-typed parts from message.content; ignore thinking/tool_use/tool_result."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for c in content:
        if not isinstance(c, dict):
            continue
        if c.get("type") == "text":
            parts.append(c.get("text", ""))
    return "\n".join(p for p in parts if p)


def _is_pure_system_reminder(text: str) -> bool:
    """Drop user messages that are entirely system-reminder envelopes."""
    s = text.strip()
    if not s.startswith("<system-reminder>"):
        return False
    if not s.endswith("</system-reminder>"):
        return False
    # If there's content after the closing tag (newline+text), it's a real message that happens to start with a reminder.
    closing = s.rfind("</system-reminder>")
    return closing == len(s) - len("</system-reminder>")


def iter_turns(jsonl_path: Path) -> Iterable[tuple[int, str, str]]:
    """Yield (turn_num, role_label, text) for each user/assistant turn in the JSONL."""
    turn_num = 0
    last_role: str | None = None
    buffered: list[tuple[int, str, list[str]]] = []

    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("type") not in ("user", "assistant"):
                continue
            msg = rec.get("message") or {}
            role = msg.get("role")
            content = msg.get("content")

            text = _extract_text_from_content(content).strip()
            if not text:
                continue

            # Drop pure system-reminder leakage from user side.
            if role == "user" and _is_pure_system_reminder(text):
                continue
            # Drop interrupt markers and command output envelopes.
            if role == "user":
                if text == "[Request interrupted by user]":
                    continue
                if text.startswith("<command-name>") or text.startswith("<command-"):
                    continue
                if _is_pasted_skill_spec(text):
                    continue

            cleaned = _clean_text_block(text)
            if not cleaned:
                continue

            if role != last_role:
                turn_num += 1
                label = "ユーザー" if role == "user" else "アシスタント"
                buffered.append((turn_num, label, [cleaned]))
                last_role = role
            else:
                buffered[-1][2].append(cleaned)

    for n, label, parts in buffered:
        yield n, label, "\n\n".join(parts)


def write_cleaned_md(jsonl_path: Path, out_path: Path, session_id: str) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with out_path.open("w", encoding="utf-8") as f:
        f.write(f"# Conversation log: {session_id}\n\n")
        f.write(f"> source: {jsonl_path}\n")
        f.write(f"> stage: 1 (deterministic)\n\n")
        for n, label, text in iter_turns(jsonl_path):
            f.write(f"---\n\n## ターン{n}: {label}\n\n")
            f.write(text)
            f.write("\n\n")
            count = n
    return count


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage 1: JSONL → cleaned md")
    ap.add_argument("jsonl", type=Path, help="path to source JSONL")
    ap.add_argument("out", type=Path, help="path to output md")
    args = ap.parse_args()

    if not args.jsonl.exists():
        print(f"error: JSONL not found: {args.jsonl}", file=sys.stderr)
        return 1

    session_id = args.jsonl.stem
    n = write_cleaned_md(args.jsonl, args.out, session_id)
    print(f"stage1: wrote {args.out} ({n} turns)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
