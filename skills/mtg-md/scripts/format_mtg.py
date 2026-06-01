#!/usr/bin/env python3
"""mtg-md: meeting-transcript → AI-optimized digest.

Two responsibilities, split into subcommands:

  detect <file>            Deterministically extract the distinct speaker
                           labels (and their counts / style), emit JSON.
                           The agent uses this to drive the "ask the user
                           for real names" phase.

  run <file>               Apply the speaker name-mapping, normalize the
      --speakers "..."     label style, then call `claude -p` to produce an
      [--out PATH]         AI-optimized, information-lossless topic digest.
      [--model NAME]       Output defaults to `<stem>_ai.md` in the SAME
      [--title STR]        directory as the input file.

Speaker labels recognized (colon may be half- or full-width, inside or
outside the bold, and may be absent):
    **西村:** text        **西村：** text
    **西村**: text        **女性:** text
    **三浦** text
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm import call_with_template  # noqa: E402

# --- speaker label patterns, tried in order ---------------------------------
# B: colon INSIDE the bold  -> **女性:** / **西村：**
_PAT_INNER = re.compile(r"^\*\*\s*([^*]+?)\s*[:：]\s*\*\*\s*(.*)$")
# A: colon OUTSIDE the bold -> **西村**: / **西村**：
_PAT_OUTER = re.compile(r"^\*\*\s*([^*]+?)\s*\*\*\s*[:：]\s*(.*)$")
# C: no colon at all        -> **三浦** text
_PAT_BARE = re.compile(r"^\*\*\s*([^*]+?)\s*\*\*\s*(.*)$")

# Labels that clearly are NOT real names -> naming phase is mandatory.
_GENERIC = re.compile(
    r"^(?:女性|男性|話者|発言者|参加者|司会|質問者|回答者"
    r"|speaker|person|spk|man|woman|male|female)"
    r"\s*[\dA-Za-z]*$",
    re.IGNORECASE,
)


def _match_label(line: str):
    """Return (raw_name, rest) if the line is a speaker label line, else None."""
    for pat in (_PAT_INNER, _PAT_OUTER, _PAT_BARE):
        m = pat.match(line)
        if m:
            return m.group(1).strip(), m.group(2)
    return None


def detect(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    counts: dict[str, int] = {}
    order: list[str] = []
    for line in text.splitlines():
        hit = _match_label(line)
        if not hit:
            continue
        name = hit[0]
        if name not in counts:
            counts[name] = 0
            order.append(name)
        counts[name] += 1

    labels = [
        {
            "raw": name,
            "count": counts[name],
            "generic": bool(_GENERIC.match(name)),
        }
        for name in order
    ]
    return {
        "file": str(path),
        "speaker_count": len(labels),
        "labels": labels,
        # If any label is generic, the agent MUST ask the user for real names.
        "naming_required": any(l["generic"] for l in labels),
    }


def _parse_speakers(spec: str | None) -> dict[str, str]:
    """'女性=西村,男性=三浦,ミウラ=三浦' -> {'女性':'西村', ...}"""
    mapping: dict[str, str] = {}
    if not spec:
        return mapping
    for pair in spec.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if "=" not in pair:
            raise ValueError(f"--speakers entry missing '=': {pair!r}")
        k, v = pair.split("=", 1)
        mapping[k.strip()] = v.strip()
    return mapping


def normalize(text: str, mapping: dict[str, str]) -> tuple[str, list[str]]:
    """Rewrite every speaker label to canonical `**<realname>:**`,
    applying the mapping (identity if a label is absent from it).
    Returns (normalized_text, sorted list of real names actually used)."""
    out_lines: list[str] = []
    used: dict[str, None] = {}
    blank_run = 0
    for line in text.splitlines():
        hit = _match_label(line)
        if hit:
            raw, rest = hit
            real = mapping.get(raw, raw)
            used[real] = None
            rest = rest.strip()
            out_lines.append(f"**{real}:** {rest}".rstrip())
            blank_run = 0
        elif line.strip() == "":
            blank_run += 1
            if blank_run <= 1:  # collapse runs of blank lines to one
                out_lines.append("")
        else:
            out_lines.append(line.rstrip())
            blank_run = 0
    return "\n".join(out_lines).strip() + "\n", list(used.keys())


def run(args: argparse.Namespace) -> int:
    src = Path(args.file)
    if not src.exists():
        print(f"error: file not found: {src}", file=sys.stderr)
        return 1

    mapping = _parse_speakers(args.speakers)
    raw_text = src.read_text(encoding="utf-8")
    normalized, participants = normalize(raw_text, mapping)

    title = args.title or src.stem
    out_path = Path(args.out) if args.out else src.with_name(f"{src.stem}_ai.md")

    result = call_with_template(
        "digest.md",
        {
            "title": title,
            "source": src.name,
            "participants": "、".join(participants) if participants else "（不明）",
            "transcript": normalized,
        },
        model=args.model,
        timeout=args.timeout,
    )

    if result.is_error:
        print(f"error: LLM call failed: {result.error_message}", file=sys.stderr)
        return 2

    out_path.write_text(result.text.strip() + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(out_path),
                "participants": participants,
                "model": result.model_used,
                "cost_usd": round(result.cost_usd, 4),
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            },
            ensure_ascii=False,
        )
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="meeting transcript -> AI digest")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("detect", help="extract speaker labels as JSON")
    d.add_argument("file")

    r = sub.add_parser("run", help="normalize + LLM-format to AI digest")
    r.add_argument("file")
    r.add_argument(
        "--speakers",
        default="",
        help='label=realname pairs, e.g. "女性=西村,男性=三浦,ミウラ=三浦"',
    )
    r.add_argument("--out", default="", help="output path (default <stem>_ai.md beside input)")
    r.add_argument("--model", default="claude-sonnet-4-6", help="model for the digest pass")
    r.add_argument("--title", default="", help="title override (default = file stem)")
    r.add_argument("--timeout", type=int, default=600)

    args = ap.parse_args()
    if args.cmd == "detect":
        print(json.dumps(detect(Path(args.file)), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "run":
        return run(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
