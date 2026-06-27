# ai-wiki command design rationale (maintenance — not loaded at runtime)

Why the active commands are shaped the way they are. Pulled out of SKILL.md: the body is a forward instruction to the executor (what to run + what each flag does); this WHY is for the maintainer. Moved here 2026-06-27 when skill-shape de-bloated the command table.

## narrative-draft
- Coverage QA skips questions whose answer is a bare citation / proper-noun (author / 文献 / 発行年): the working-hypothesis tree deliberately omits those, so asking would impose a structural coverage ceiling.
- Coverage judging runs on a different model from the opus generator (`--judge-model`, default sonnet): dodges self-preference bias / reward hacking when a model grades its own output. Generation + gap-fix stay on opus.
- Hold-out (`holdout_coverage_pct`): after the fix loop converges, coverage is re-measured on a fresh independent QA set the fixer never optimized against — the honest out-of-sample number vs the optimized in-sample `coverage_pct`.
- Source archival: the stored source `.md` is the immutable verify-against truth (hard rule #3), matched by absolute path so re-running never duplicates it.
- `--faithfulness`: precision direction, complements coverage's recall; judged by a different model to avoid self-preference bias.

## derivation-scan
- Sets scope even when the source omits the derivation: a result is a target whether or not its steps are present; skip markers ("略"/"面倒"/"補足参照"/"left as an exercise") flag the hard, high-value ones the source dodged.

## derivation-draft
- Generator (opus) drafts from the source (the algebra's source of truth); the anchor narrative supplies only the subgoal structure — building a spine from the tree's 1-3-sentence nodes would hallucinate steps. A different judge model verifies each step (same self-preference-bias avoidance as coverage/faithfulness).

## subject-dag-render
- JSON is the single source of truth; rendering from it (HTML untouched by hand) kills JSON/HTML double-keeping drift.
