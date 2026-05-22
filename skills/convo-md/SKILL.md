---
name: convo-md
description: Distill the current Claude Code conversation log (JSONL) into a compact markdown file that another AI can cold-start from. Three stages — Stage 1 deterministic noise removal (Downloads link blocks, completion-report boilerplate, pasted skill specs, citation blocks), Stage 2 chunked parallel Haiku compression with selectable level (light/medium/aggressive), Stage 3 hierarchical overview prepended to the top so a fresh AI can grasp the entire session in 1-2 minutes. Auto-detects the current session JSONL from cwd. Invoke when user wants to hand off a long Claude Code conversation to a fresh session without paying full token cost or losing signal.
---

# convo-md

Conversation log → handoff-ready md. Reads the JSONL of the **current session** (auto-detected from cwd), runs deterministic denoise + chunked LLM compression + hierarchical overview, writes a single md.

## Output invariants

1. **Per-turn format preserved.** `## ターンN: ロール` headings stay; turn numbers are never renumbered.
2. **User messages are sacred.** Stage 2 LLM must not alter user text (even in aggressive mode).
3. **Stage 3 overview is additive.** Detailed log below is not re-summarized in cross-chunk synthesis; Stage 3 reads Stage 2 output and extracts a separate overview at the top.

## Stages

- **Stage 1 (deterministic, instant)**: strip thinking/tool blocks, system-reminders, Downloads link bullets, completion boilerplate, pasted skill specs.
- **Stage 2 (Haiku chunked, parallel)**: 20-turn chunks, each compressed by Haiku per prompt template. Level controls aggressiveness:
  - `light` — preserves nearly everything, target ratio ~0.8 (original safe behavior).
  - `medium` (default) — aggressively compresses assistant prose, drops rejected proposal bodies, target ratio ~0.4-0.5.
  - `aggressive` — each assistant turn becomes 3-7 bullets; rejected code → 1-line summary; tables of inspection data → summary. Target ratio ~0.15-0.2.
- **Stage 3 (Haiku single call, optional)**: reads Stage 2 output, generates a `## 全体サマリ` section (300-600 lines) prepended to the top with: セッション概要 / 主要トピック / 採用決定 / 却下案 / 重要ファイル変更 / 未解決事項 / 重要な発見.

## Command

```bash
python3 ~/.claude/skills/convo-md/scripts/distill.py \
    [--out PATH] [--no-stage2] [--no-stage3] \
    [--level light|medium|aggressive] \
    [--chunk-size N] [--overlap N] \
    [--model NAME] [--parallelism N] [--timeout SEC] \
    [--jsonl PATH]
```

Defaults:
- `--out` → `<cwd>/claude_sessions/log_<end-time>.md` (folder auto-created with stub README). End time = last message timestamp in JSONL, JST, `YYYY-MM-DD_HH-MM-SS`. Descending order = newest first.
- `--level` `medium` (good ratio/quality balance; switch to `light` for fidelity-critical sessions or `aggressive` for sub-1000-line outputs)
- `--chunk-size` 20 turns, `--overlap` 2 turns
- `--model` `claude-haiku-4-5-20251001`, `--parallelism` 6, `--timeout` 600s
- `--jsonl` auto-detect (cwd-encoded dir first, then scans recent JSONLs by their `cwd` field)
- `--no-stage2` skip LLM compression, output Stage 1 only (no Stage 3 either)
- `--no-stage3` skip Stage 3 overview, output Stage 1+2 only