# compress_chunk_aggressive v1.0

## System

You compress a chunk of a Claude Code conversation log to a **highly distilled form**. Each turn becomes 3-7 lines of bullet points capturing only what a future AI needs to continue this conversation cold. Target: ~15-20% of input size.

The input format uses `## ターンN: ロール` headings. Your output uses the same format and turn numbers; you radically shorten content within turns.

## User

Compress the chunk below aggressively. Strict rules:

**Output format**
- Same `## ターンN: ロール` headings, same turn numbers, same `---` separators between turns.
- Output ONLY turns {{TURN_START}}-{{TURN_END}}. Any earlier turns shown for context must NOT appear in your output.
- Each compressed turn is **3-7 bullet points** (or fewer if the original turn is short).

**Compression rules**

For **user turns**:
- If 1-3 lines: output VERBATIM (short user messages are signal).
- If longer: keep verbatim — user messages are sacred even in aggressive mode.

For **assistant turns**:
- Replace prose with bullets covering:
  - **Decisions / Recommendations made**: 1-2 lines
  - **Files/functions/paths mentioned**: comma-separated list
  - **Key technical points**: 1-3 lines
  - **Open questions / next actions**: 1 line
  - **Critical data values**: dates, counts, percentages preserved

For **code blocks**:
- If code was **adopted** (committed/applied): replace body with `参考: ファイル名 + 1-line description` and a 3-5 line snippet of just the key change. Full code is in git history.
- If code was **proposed but not yet decided**: keep up to 10 lines, summarize the rest as `(... 残り N 行: <one-line gist>)`.
- If code was **rejected**: replace with `（提案コード省略: {reason}）`.

For **tables**:
- Tables comparing options: keep the table but only the columns that matter for the decision.
- Tables of detailed inspection results (e.g., per-row data): replace with `（{N} 行のテーブル: <one-line summary>）`.

For **proposal/comparison lists (A/B/C/D)**:
- After user picks one: `採用: 案A (理由: ...)` 一行 + bullet of the chosen option's content. Other options omitted.
- If still unresolved: keep top-line of each option (no body).

**Never modify**
- User messages (verbatim).
- The user's preferences, corrections, emotional reactions (e.g., 「OK」「やめて」「いや」, short questions).
- Exact numerical values, dates, file paths, function names.
- Commit messages and git operations.

**Drop completely**
- Verbose "ここがポイント" / "重要なのは" emphasis prose.
- "以下に詳しく説明します" type framing sentences.
- Repeated explanations of the same concept.
- Output of tool calls if they appear inline (assistant retransmits) — assume the user has read them.
- Long apology/acknowledgment text from the assistant ("すみません、ありがとうございます" 等の儀礼).

**Retention checklist** — before you finalize a turn, scan the original and ensure these survive:

- User intent
- **Adopted** decision (1 line) + reasoning (1 line)
- File names, function names, paths, sample counts, dates, numbers
- Open questions / next actions
- Rejected approach + one-word reason (e.g., 「過剰設計」「コスト」)

**Chunk to process**

You will receive turns {{CONTEXT_START}} through {{TURN_END}} below. Turns {{CONTEXT_START}}-{{CONTEXT_PREV_END}} (if any) are CONTEXT ONLY — do not include them. Output only turns {{TURN_START}}-{{TURN_END}}.

```markdown
{{CHUNK_TEXT}}
```

Output the aggressively compressed chunk now. Begin directly with `---\n\n## ターン{{TURN_START}}:` and end after the last line of turn {{TURN_END}}. No preamble, no explanation.
