# compress_chunk_light v1.0

## System

You compress a chunk of a Claude Code conversation log. The input format uses `## ターンN: ロール` headings for each turn. Your output uses the EXACT same format and turn numbers — you only shorten content within turns. You operate on a single chunk in isolation; you do not see other chunks.

Your goal: reduce token count by removing locally-redundant content WITHOUT losing signal that a future AI would need to continue this conversation cold.

## User

Compress the chunk below. Strict rules:

**Output format**
- Same `## ターンN: ロール` headings, same turn numbers, same `---` separators between turns.
- Output ONLY turns {{TURN_START}}-{{TURN_END}}. Any earlier turns shown for context must NOT appear in your output.
- No new sections, no global summary, no per-turn one-line annotations.

**Never modify**
- User messages — output them VERBATIM, character-for-character.
- Decisions made by the assistant (the final adopted wording of any change/proposal).
- Code blocks, file paths, function names, technical terms.
- Numerical values, dates, sample counts.

**Operations you MAY perform** (only when clearly applicable within this chunk):

1. **Drop unchosen options** — When the assistant proposes (A)/(B)/(C)/(D) and within this same chunk the user picks one (e.g., user replies with the chosen letter or a short affirmative right after), you may delete the bodies of the unchosen options. Keep the chosen option's full text and the assistant's recommendation reasoning. Replace deleted options with one line: `（採用されなかった案 (B)(C) は省略）`.

2. **Compress pure CSS/style micro-tuning turns** — If an assistant turn is ENTIRELY about pixel-level visual adjustments (font size, color, padding) and contains no design judgment, replace its body with one line: `（スタイル微調整: <one-phrase neutral summary>）`. Do NOT do this if the turn contains any non-style content.

3. **Merge duplicate concept explanations** within this chunk — If a concept is explained in detail more than once in this chunk, keep the first full explanation and replace later detailed re-explanations with `（前述の通り）`. Brief mentions (one sentence) are not "detailed re-explanations" and should stay.

4. **Drop residual deterministic noise** — Trailing standalone lines like `反映完了。`, `完了しました。`, `Now generate PDF:`, or trailing Downloads link bullets that escaped Stage 1.

**Operations you MUST NOT perform**

- Do NOT renumber turns.
- Do NOT compress technical/design decisions, design rationale, or the user's preferences/corrections/emotional reactions — these are signal.
- Do NOT generate any global summary, table of contents, or per-turn annotation.
- Do NOT cross chunk boundaries: if a decision references a proposal made outside this chunk, leave the reference untouched.

**Retention checklist** — before you finalize a turn's compression, scan the original turn for any of these and ensure they survive in your output:

- User intent / what the user is trying to achieve
- Technical or design decisions and the reasoning behind them
- File names, paths, feature names, function names, sample counts
- Rejected approaches with explicit "why not" reasoning
- Open questions / unresolved points
- Next-action items
- User preferences, corrections, emotional reactions (any short user expression of dissatisfaction, agreement, or surprise)

**Chunk to process**

You will receive turns {{CONTEXT_START}} through {{TURN_END}} below. Turns {{CONTEXT_START}}-{{CONTEXT_PREV_END}} (if any) are CONTEXT ONLY — you may use them to understand decisions, but DO NOT include them in your output. Output only turns {{TURN_START}}-{{TURN_END}}.

```markdown
{{CHUNK_TEXT}}
```

Output the compressed chunk now. Begin directly with `---\n\n## ターン{{TURN_START}}:` and end after the last line of turn {{TURN_END}}. No preamble, no explanation.
