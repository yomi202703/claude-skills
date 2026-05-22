#!/usr/bin/env python3
"""Stage 3: Stage 2 出力を再投入し、全体サマリを生成して最終 md の頭に挿入。

Anthropic 公式の hierarchical summarization アーキテクチャを採用:
  Stage 1 (deterministic) → Stage 2 (chunk 圧縮) → Stage 3 (全体サマリ)

最終 md の構造:
  preamble
  ⭐ 全体サマリ (Stage 3, ~300-600 行)
  ---
  詳細ログ (Stage 2 出力)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Local import.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm import call_with_template  # noqa: E402


def run_stage3(
    stage2_md: Path,
    out_path: Path,
    *,
    model: str = "claude-haiku-4-5-20251001",
    timeout: int = 600,
) -> dict:
    """Stage 2 出力を読んで overview を生成し、Stage 2 内容と合体させて out_path に書く。

    Args:
        stage2_md: Stage 2 の出力 md (preamble + 圧縮ターン群)
        out_path: 最終 md 出力先 (stage2_md と同じパスでも OK)
    """
    text = stage2_md.read_text(encoding="utf-8")

    # preamble (最初の '---' まで) と本文を分離
    sep_idx = text.find("\n---\n")
    if sep_idx == -1:
        # 分離不能なら全体を本文扱い
        preamble = ""
        body = text
    else:
        preamble = text[:sep_idx].rstrip() + "\n\n"
        body = text[sep_idx + 1:]  # '---\n' の '\n' を残す

    template_path = Path(__file__).resolve().parent / "prompts" / "compress_overview.md"
    if not template_path.exists():
        raise FileNotFoundError(f"prompt template not found: {template_path}")

    result = call_with_template(
        template_path,
        {"COMPRESSED_LOG": body},
        model=model,
        timeout=timeout,
    )

    if result.is_error:
        return {
            "stage3": "error",
            "error_message": result.error_message,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "cost_usd": result.cost_usd,
        }

    overview = result.text.strip()

    # 最終 md: preamble + overview + body
    # preamble の stage 行を更新
    preamble_lines = preamble.rstrip().splitlines()
    stage_line = next((l for l in preamble_lines if l.strip().startswith("> stages")), None)
    if stage_line:
        new_stage_line = stage_line.rstrip() + " + stage3"
        preamble_lines = [new_stage_line if l == stage_line else l for l in preamble_lines]
    new_preamble = "\n".join(preamble_lines) + "\n\n"

    final = new_preamble + overview + "\n\n" + body.lstrip()
    out_path.write_text(final, encoding="utf-8")

    return {
        "stage3": "ok",
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "cost_usd": result.cost_usd,
        "duration_ms": result.duration_ms,
        "overview_chars": len(overview),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage 3: hierarchical overview generation")
    ap.add_argument("stage2_md", type=Path, help="Stage 2 出力 md")
    ap.add_argument("out", type=Path, help="最終 md 出力先")
    ap.add_argument("--model", default="claude-haiku-4-5-20251001")
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()

    if not args.stage2_md.exists():
        print(f"error: {args.stage2_md} not found", file=sys.stderr)
        return 1

    summary = run_stage3(
        args.stage2_md,
        args.out,
        model=args.model,
        timeout=args.timeout,
    )
    import json
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary.get("stage3") == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
