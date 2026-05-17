---
name: deadcode
description: Detect dead code, verify it, delete it, and confirm with tests — end to end. Trigger on "find dead code", "unused code", "unreferenced", "clean up", "remove unused", "dead functions".
---

# deadcode (router)

The user does not read code. The skill completes end to end.
Never escalate "needs review" items to the user. Never treat tool output as the final verdict.

## Rules

R1. Passing tests is the sole gate for deletion.
R2. Make a safety commit before any deletion.
R3. Tool output is a candidate list. Final judgment is by the skill's own grep + code reading.
R4. "Zero dead reports" does not mean "no dead code exists".

## Phase 0 — Stack detection & route

| manifest | language | framework file |
|----------|----------|----------------|
| `package.json` | JS/TS | `frameworks/js-ts.md` |
| `pyproject.toml` / `requirements.txt` | Python | `frameworks/python.md` |
| `go.mod` | Go | `frameworks/go.md` |
| `Cargo.toml` | Rust | `frameworks/rust.md` |
| `composer.json` | PHP | `frameworks/php.md` |

Multi-language repo: ask via AskUserQuestion to pick one.

Load `LENSES`, `TEST_CMD`, `FRAMEWORK_HOOKS`, `ENTRYPOINTS` from the framework file.

## Phase 1 — Baseline & safety commit

1. Run `TEST_CMD`
   - exit 0 → continue
   - no tests configured → AskUserQuestion: "No tests found. Proceed conservatively with grep + typecheck only?". yes → replace R1 with "grep + typecheck green" (`status: no_tests_conservative`)
   - exit ≠ 0 → exit with `status: tests_red_before_start`
2. `git add -A && git commit -m "wip: pre-deadcode-scan snapshot" --allow-empty`
3. Run **all `LENSES` in parallel**, UNION the outputs, dedup by `(file, line, name)`. Each lens has `name` and `safety` (1 = safest, 3 = riskiest). Carry `lens` and `safety` on every finding. If any lens command is `command not found`, AskUserQuestion to run `bash ~/.claude/skills/deadcode/setup.sh --<lang>`. no → `status: aborted_no_tool`

Output schema: `[{file, line, name, kind, lens, safety}]`.

## Phase 2 — Per-finding verification

For each finding, decide silently (do not surface to user):

1. Read the definition site (±20 lines)
2. `rg -n '\b<name>\b'` repo-wide
3. Filter grep output: drop the definition line; drop comment lines; keep string-literal hits. ≥1 line remaining → keep alive, skip
4. Match against `FRAMEWORK_HOOKS` → skip
5. `rg -n "['\"]<name>['\"]"` for dispatcher patterns. ≥1 hit → skip
6. None matched → add to deletion list

## Phase 3 — Batch delete + bisect

### 3a — Stack N commits (sorted safest first)

Sort `deletion_list` by `safety` ascending (1 → 3). This puts unreachable-code and unused-import deletions first; aggressive function/class removals last. If bisect later finds a bad commit, the earlier (safer) ones are more likely to stay.

```
for c in sorted(deletion_list, by safety):
    delete(c)             # imports/vars via Edit, functions/methods/classes via ast-grep
    typecheck             # pyright / tsc / cargo check / go vet
    pass → git commit -m "deadcode: try remove <file>:<name> [lens=<lens>]"
    fail → git reset --hard HEAD, record in rejected_by_typecheck
```

### 3b — Single test pass + bisect

```
TEST_CMD
```

green → accept all, go to Phase 4.
red → `git bisect start HEAD <safety_commit> && git bisect run TEST_CMD` to find bad commit → `git revert --no-edit <bad>` → rerun TEST_CMD → repeat until green. Record in `rejected_by_test`.

### 3c — AST delete (functions/methods/classes)

```
ast-grep run --pattern '<pattern>' --rewrite '' --lang <lang> <file>
```

## Phase 4 — Final commit & report

If ≥1 deletion:

```
git add -A && git commit -m "deadcode: remove N unused <kind>"
```

Report:

```
status: completed | aborted_no_tool | tests_red_before_start | no_tests_conservative
safety_commit: <SHA>
deletion_commit: <SHA> or null
removed: [{file, name, kind}]
rejected_by_test: [{file, name, kind}]
rejected_by_typecheck: [{file, name, kind}]
limitations: <free text>
revert_cmd: "git reset --hard <safety_commit>"
```
