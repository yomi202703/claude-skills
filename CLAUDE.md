# Global working preferences

These apply across every repository. A repo's own CLAUDE.md adds repo-specific detail and overrides these where they conflict.

## Output style

- No `**` bold emphasis. Structure with `#` headings and `-` bullets only.

## Documentation governance

When a repo keeps working docs, give them four roles and do not blur them:

- TODO = future / execution queue. Single source of truth for what is next. Two states only — Active (actionable now, ranked P0–P2) and Deferred (blocked; each item MUST name the concrete trigger that unblocks it, e.g. "[data X arrives]", "[owner decides]"). One line per item; rationale lives in decisions, never here. Delete when done.
- STATUS = current snapshot. Rewritten each session. Keep it short.
- decisions = append-only ADR ledger. Why a choice was made and what happened. Never rewrite past entries. May be split into one append-only file per topic (mirroring the repo's modules) once a single ledger grows large enough to bloat context on read — the point of the split is that you open only the relevant topic file, not the whole history. When split, freeze the pre-split monolith in archive and route new entries to the topic files; pointers name the topic (e.g. "decisions/<topic> <date>"). Routing a new entry to its topic is the writer's (the AI's) judgment call — do not ask the user which file; default to the cross-cutting bucket when unsure.
- archive = frozen history. Reference only.

Completed work moves from TODO to decisions. It is not left checked-off in TODO. State (Active/Deferred) is orthogonal to priority: an item can be important yet Deferred because it is blocked. A Deferred item with no concrete trigger is not deferred — it is either Active or a "won't do". A "won't do" is recorded in decisions only (the dated call, with rationale) and removed from TODO — do NOT keep a "won't-do" index in TODO (it duplicates decisions and bloats the queue). When you need the list of rejected items to avoid re-proposing one, grep decisions (and archive) for the dated "won't do" calls before proposing.

## Session start

At the start of each session, orient from the repo's governance docs — read-only (surface, do not fix):

- Read in order: STATUS (where we are) → TODO (next + blockers) → the last few decisions (recent why) → narrative tail if the repo has that role → README. If none exist, point to /claude-md.
- While reading, flag inconsistencies you are confident about: completed work left in TODO Active; Deferred items with no unblock trigger; STATUS↔TODO contradiction; STATUS older than the latest decision; rationale hoarded in TODO instead of decisions; and — if a `.lavish/` workspace exists — its views looking stale vs the docs (point to /throughline to refresh).

## Human-facing view layer (throughline / lavish)

This is additive and does not redefine the four-role doc governance above.

- Make the human's surface a read-only browser HTML, not terminal scrollback. A repo may keep a `.lavish/` workspace — a standing logic view: how it works now (source → output dataflow, structure, and the verbatim full text of any prompt that drives the mechanism). At junctures (a chunk closed, the mechanism changed), `/throughline` regenerates it from the code/design. (The earlier second pane — a flow view of how-we-got-here — was dropped; it went unread. That trail lives in decisions.)
- view ≠ truth. Truth stays in decisions/TODO/code; the view is a generated window onto it. Freshness is a content hash of the source (stale-detectable); do not build auto-refresh (regenerate scrappily). Keep the explanatory prose plain — a general engineer's level, no internal jargon — but embed any driving prompt verbatim, full text, as quoted evidence (that block alone is exempt from the plain-language rule).
- Cross-project: the views currently running across projects are aggregated at `~/.lavish/home.sh` (localhost:8076 — scans live localhost view-servers; serve a repo's workspace and it shows up).
- The repo-local 5th "narrative" role (durable, append-only frozen flow) stays repo-local unless explicitly promoted. Origin/design: the agentic-engineering repo's decisions (lavish-*/throughline-*/narrative-*).

## Do it yourself

- Prefer reading and exploring directly over spawning subagents whose summaries drop information. Delegate for breadth (fan-out search), not for judgments that should be grounded in primary sources.
- Use grep/find to locate where something is, then open and read the file before concluding. Do not conclude from a line snippet alone.

## Writing prompts for LLM executors

Four rules when authoring or editing a prompt that an LLM will execute (judge, extract, classify, etc.):

1. No prompt-induced bias. Do not nudge toward a verdict with emphasis, authority framing, embedded meta-rationale, or agreement-seeking phrasing. State the rule neutrally.
2. Eval-pipeline integrity. Never put ground-truth, expected answers, or eval-framework terms into the executor's prompt.
3. No overfitting. Do not encode specific id-to-verdict pairs, named entities, or contact ids. Keep few-shot examples to one or two, and abstract.
4. Termination and verification spec. Define done: success and failure return shapes, allowed inputs, output path, and read/tool-failure behavior. Pair every prohibition with a positive operational alternative.
