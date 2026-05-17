# Token-consumption spike log — xlsx skill self-improve iter4 resume (2026-04-19)

Recording notably large tool outputs during this loop, root cause, and mitigation.

## Entry 1 — Row width inspection, プランコード rows 15-49

- **Tool**: `Bash` (python heredoc)
- **Intent**: Inspect row widths / lengths r15-r49 in プランコード sheet to understand why hdr was selected at r39
- **Output size**: ~35 lines, each ~55 chars → ~2 KB
- **Cause**: Moderate — loop over 35 rows. Lens-only (no raw cell values), which kept it bounded. If I'd printed raw values, r20's 5KB spec cells would have multiplied this by ~500x.
- **Status**: Acceptable. Lens-only discipline paid off directly.
- **Mitigation (for next similar inspection)**: Stay lens-only. If narrowing further needed, dump to /tmp and grep for specific row.

## Entry 2 — Candidate-score debug dump

- **Tool**: `Bash` (python heredoc, ~60 lines)
- **Intent**: Replay the detect_header_row scoring locally to see why r39 beats r22
- **Output size**: ~10 lines → <1 KB output, but heredoc *input* was ~2 KB
- **Cause**: The heredoc re-implements logic from xlsx_classify.py inline. Input is not free — it sits in context.
- **Mitigation**: For repeated debugging, consider adding a tiny `--debug-headers` flag to `xlsx_classify.py` so we call the existing code instead of re-pasting it. Lower token cost across iterations.

## Entry 3 — Two regressions on 補償基準DB required 2 extra harness runs

- **Tool**: `Bash` (harness.py, via hook + manual) ×2
- **Intent**: Verify 11/11 pass after each of 3 iterative edits
- **Output size**: Each harness run ≈ 14 lines → ~1 KB × 3 = ~3 KB. Plus 2 hook blocking messages with full table → ~3 KB each.
- **Cause**: Jumped ahead by bulk-removing short_cnt without first checking whether 補償基準DB DB-style headers depended on it. Two hook regressions were avoidable with a 30-second read of the baselines first.
- **Mitigation**: Before deleting an existing feature, grep the baselines / check at least one file that might depend on it. Prefer incremental: add new features first, verify improvement, THEN tune existing weights.

## Entry 4 — Score-debug Python heredoc, 2 replays

- **Tool**: `Bash` (python heredoc) ×2
- **Intent**: Replay classify scoring on プランコード / 対象外_無条件 to see why r22/r1 loses
- **Output size**: ~12 lines each, ~2 KB
- **Heredoc input size**: ~2 KB × 2 = ~4 KB
- **Cause**: Re-implementing widths computation inline each time instead of exposing a debug flag in xlsx_classify.py
- **Mitigation (deferred)**: Add `--debug-headers` flag that prints top-5 candidate scores for every sheet. Small code cost, saves tokens on every future header-tuning iteration.

## Entry 5 — post_spec_block overshoot on 対象 sheet

- **Tool**: `Bash` (single classify + 6-row cell-length inspection)
- **Intent**: Understand why 対象 sheet's 対象 → hdr=[24] after adding post_spec_block feature
- **Output size**: ~10 lines
- **Cause**: Added feature fired on drug-info rows with 519-char text cells (false positive). Fix: require ≥2 long cells (real spec blocks span multi-column prose, data-with-long-text is a single dominant cell).
- **Mitigation**: After adding a coarse feature, always test on at least 1 "looks similar but shouldn't fire" case. Cost of this iteration: 1 extra regression, ~2 KB debug. Would have been zero if I'd tested 対象 BEFORE wiring the feature.

## Watch list going forward

- Subagent E2E report (task #5): cap at ≤500 words in the prompt and demand summary format, not raw outputs.
- Baseline regeneration (task #6): redirect to disk, don't print.
- If I add the longest-run-start heuristic, verify by re-running classify on **one file only**, then harness. No bulk re-run across files from the parent conversation.
