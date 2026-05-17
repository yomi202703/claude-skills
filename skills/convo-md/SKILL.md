---
name: convo-md
description: Distill the current Claude Code conversation log (JSONL) into a compact markdown file that another AI can cold-start from. Two stages — Stage 1 deterministic noise removal (Downloads link blocks, completion-report boilerplate, pasted skill specs, citation blocks), Stage 2 chunked parallel Haiku compression with a retention-bucket checklist (user intent / decisions / files / rejected options / open questions / next actions). Auto-detects the current session JSONL from cwd. Invoke when user wants to hand off a long Claude Code conversation to a fresh session without paying full token cost or losing signal — typical trigger: "この会話を md にして", "/convo-md", "別トークに移りたいから会話ログを書き出して".
---

# convo-md (v1)

Conversation log → handoff-ready md. Reads the JSONL of the **current session** (auto-detected from cwd), runs deterministic denoise + chunked LLM compression, writes a single md.

## Output invariants

1. **Per-turn format preserved.** `## ターンN: ロール` headings stay; turn numbers are never renumbered.
2. **User messages are sacred.** Stage 2 LLM must not alter user text.
3. **No global summary.** Stage 2 reasons within each chunk only; no cross-chunk synthesis, no per-turn one-liner annotations.

## Command

```bash
python3 ~/.claude/skills/convo-md/scripts/distill.py \
    [--out PATH] [--no-stage2] \
    [--chunk-size N] [--overlap N] \
    [--model NAME] [--parallelism N] [--timeout SEC] \
    [--jsonl PATH]
```

Defaults:
- `--out` → `<cwd>/claude_sessions/log_<end-time>.md` (folder auto-created with stub README). End time = last message timestamp in JSONL, JST, `YYYY-MM-DD_HH-MM-SS`. Descending order = newest first.
- `--chunk-size` 20 turns, `--overlap` 2 turns
- `--model` `claude-haiku-4-5-20251001`, `--parallelism` 6, `--timeout` 600s
- `--jsonl` auto-detect (cwd-encoded dir first, then scans recent JSONLs by their `cwd` field)
- `--no-stage2` skip LLM compression, output Stage 1 only

## Typical flow

User in a long session:
```
> /convo-md
```
Claude invokes `distill.py`, reports the output path. User opens new session and feeds the md as initial context.
