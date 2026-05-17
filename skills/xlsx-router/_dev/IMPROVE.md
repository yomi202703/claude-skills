# Self-improvement protocol for xlsx

Event-driven, not periodic. The skill does not drift over time.

## Triggers (the only valid ones)

1. **Skill edit** — PostToolUse hook (`_dev/hook_check.sh`) auto-runs `pytest tests/`. Regressions block the edit.
2. **New corpus file** — `cp <real.xlsx> corpus/ && pytest tests/ -q`. First run writes a fresh golden to `tests/test_classify_regression/<basename>.yml` and fails; inspect the golden, re-run to confirm pass, commit. If output is buggy, enter the repair loop.
3. **Explicit improvement request** — manual repair loop.

## Pre-flight

See `~/.claude/selfimprove/PREREQS.md`. Verify pytest / hypothesis / pytest-regressions are globally callable and the hook is installed.

## Process rules

Follow `feedback_selfimprove_loop_hygiene.md` (user memory). It's the single source for sequential-processing / token-spike logging / meta-check / autonomy / downstream-consumer rules. Don't re-state them here.

## Repair loop

1. Run pytest → green? exit. Else continue.
2. Diagnose — which test, which file, which sheet.
3. Meta-check — symptom or abstraction wrong? If the latter, surface and escalate.
4. Fix surgically. Don't add features to `xlsx_classify.py` unless a new corpus file forces it.
5. Re-run pytest (hook auto-fires on save). Confirm green.
6. **LLM-eval** when materialize or docs changed — spawn ONE subagent, have it answer factual questions from the artifact. Target ≥90%.
7. **Fresh-Claude skill-usage check** when corpus grew, SKILL.md/docs changed, or a refactor landed — spawn ONE subagent with a raw "extract this xlsx" task and no priming. If they can't discover the skill, pick the wrong path, or produce worse output than the designed flow → SKILL.md / docs defect to fix. Rationale and concrete iter5.1 example: `feedback_selfimprove_loop_hygiene.md` rule 2.5.
8. Append to `history/CHANGELOG.md` — date, target, why, accepted/rolled-back.

## STOP safety rails

The loop MUST NOT edit:
- `_dev/corpus/` (would overfit)
- `_dev/tests/test_classify_regression/*.yml` (would make regressions lie)
- `_dev/IMPROVE.md` or `_dev/hook_check.sh` (the loop itself)
- `~/.claude/selfimprove/` (shared infra)

May freely edit: `SKILL.md`, `scripts/*`, `docs/*`, `templates/*`.

## Convergence

Stop when:
- All tests pass, no new corpus pending
- Same failure signature 3× (oscillation — meta-check should have caught earlier)
- Diff > 2× skill LOC (reconsider scope)
- 2h wall-clock reached
