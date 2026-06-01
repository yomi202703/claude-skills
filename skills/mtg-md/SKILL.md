---
name: mtg-md
description: Turn a meeting-transcript markdown (audio ASR → md, e.g. the non-wecom files under 50_MTG_wecom — speakers labeled **西村:** / **女性:** / **ミウラ：** etc.) into an AI-optimized, information-lossless topic digest for a downstream AI to consume. Handles mixed speaker-label styles (colon inside/outside bold, half/full-width), removes ASR filler at "standard" strength, and normalizes speakers to real names. ALWAYS runs an interactive speaker-naming phase before formatting. Output is written beside the input as <stem>_ai.md. NOT for Claude Code conversation logs (use convo-md) and NOT for chat exports like wecom.
---

# mtg-md

Meeting transcript md → AI digest. Reader is an **AI, not a human**: prioritize information completeness and structure over readability. Summarizing/condensing is allowed; **losing any fact, number, decision, todo, or concern is not.**

## Pipeline (agent-orchestrated)

The agent drives 4 steps. Steps 2–3 are an **interactive speaker-naming phase that must not be skipped** — the whole point of this skill is producing real-name output.

### 1. Resolve input

One or more transcript `.md` files. For a directory, glob `*.md` and exclude obvious non-transcripts (e.g. `wecom_*`, already-produced `*_ai.md`).

### 2. Detect speakers

```bash
python3 ~/.claude/skills/mtg-md/scripts/format_mtg.py detect <file>
```

Returns JSON: each distinct speaker `label` with `count` and `generic` (true for 女性/男性/話者A/Speaker1…), plus `naming_required`.

### 3. Ask the user for real names (the naming phase)

Always present the detected labels and **ask the user to map each to a real name** (use `AskUserQuestion`). Guidance:
- `naming_required: true` (generic labels like 女性/男性) → mapping is mandatory; do not guess.
- Labels that already look like real names → still confirm; offer "keep as-is" as the default, and let the user unify variants (e.g. `ミウラ`→`三浦`, full/half-width).
- If the same person appears under several labels, map them all to one canonical name.
- Process one file at a time, or reuse a confirmed mapping across files from the same project when labels match.

Build the `--speakers` spec from the answers: `"女性=西村,男性=三浦,ミウラ=三浦"`. Labels not in the spec pass through unchanged.

### 4. Run the digest

```bash
python3 ~/.claude/skills/mtg-md/scripts/format_mtg.py run <file> \
    --speakers "女性=西村,男性=三浦" \
    [--out PATH] [--model NAME] [--title STR]
```

- Deterministic prep: rewrite every speaker label to canonical `**<realname>:**`, apply the mapping, collapse blank-line runs.
- LLM pass (`claude -p`, default `claude-sonnet-4-6`) emits the digest per `prompts/digest.md`.
- **Output: `<stem>_ai.md` in the SAME directory as the input** unless `--out` is given. Prints JSON with `out`, `participants`, `cost_usd`, tokens.

Report the output path(s) to the user when done.

## Output shape

`prompts/digest.md` defines it: 会議メタ → トピック別ダイジェスト (per-topic: 議論の流れ / 事実・数値 / 決定事項 / 保留・宿題 / 重要発言の原文引用) → 決定事項 → ToDo・宿題 → 未解決の論点 → 固有名詞・用語集. Filler (ふんふん/えーっと…) is dropped, but decision-bearing acknowledgements ("はい、お願いします") are kept. Uncertain ASR on proper nouns is flagged `（要確認: 原文「…」）`.

## Scope / non-goals

- For Claude Code session logs → **convo-md**.
- For chat exports (wecom etc.) → out of scope; this expects spoken-meeting transcripts with `**speaker:**` turn labels.
- Default model is `claude-sonnet-4-6` (info-loss is the cardinal sin; Haiku may drop nuance). Files here are single-call sized; no chunking yet.
