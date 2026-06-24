# Discovery drill (chat-time behavior)

Use when the user wants to learn a tree for the first time — not be quizzed on what
they already know. This is the front of the learning pipeline. You (the main
assistant) run it in chat; there is no `dispatcher.py` command — it is judgment
(posing the stumble, diagnosing the divergence, withholding the answer), not a script.

## What it is and why

Reading a finished tree and nodding is low-density: the learner absorbs the solution
without ever feeling the problem that made it necessary. So hand them the problem and
make them reconstruct the resolution before they see it. Every narrative node is
written problem-first (`[?] … ⇒`); every DAG edge is a `⟳ だから次の問題`.

Everything downstream trains already-acquired material: retention → `card-draft` →
Anki SRS; procedural reproduction → faded derivation drill
(`reference/derivation-drill.md`). Discovery is where understanding is first built.

Grounding: epistemological obstacles (Bachelard), the genetic/historical method,
productive failure (Kapur — struggle-then-instruction beats instruction-then-practice,
but only when the learner has the raw materials to take a step), guided discovery with
a faded-worked-example ladder.

## Invariants

1. Sealed answer key. You open `narratives/<slug>.md`; the learner never sees it until
   they commit. No reveal-before-commit, ever. "分からない" is a valid commit.
2. On a wrong/partial answer, give only why their path diverges — backward-looking,
   about the path they committed. Never the correct answer, and never a forward
   pointer (the next move, the tool to use, where to look). Reward the on-target
   thread, then re-pose the same edge. Closing the last gap is the learner's job —
   this is what separates discovery from lecturing.
3. Hints are pull, never push. Add scaffold only when the learner asks ("ヒント"), one
   notch at a time; raise the fade back once they recover. Never volunteer it. When
   unsure, give less and wait — silence is allowed. Default to under-helping.

Before sending any diagnosis, strip every sentence that points toward the answer.

## The DAG generates the questions

Traverse `maps/<subject>-dag.json` in topological order, never ahead of a node's
parents (`ai_usage`: confirm parents first, then work from `desc` + the `trees` it
points to; add nothing the trees don't contain). Each edge is one stumble question;
its `kind` fixes the type:

- `flow` — stand the learner at the parent with only the parent's tools, pose the gap
  that forces the child. ("Given p=MC for a price-taker — now the firm can *set*
  price. What quantity does it pick?")
- `join` — "you hold these N pieces (demand height = MU, supply = MC) — what can you
  build that none gives alone?" The convergence is the insight.
- `fan` — the deepest stumbles. Name the maintained assumption, drop it, ask what
  breaks (price-taker → monopoly; independent choice → strategic interdependence →
  game theory).
- `cross` / tool-injection — pose the inadequacy that makes importing an outside tool
  necessary, before naming it.

## Drill loop — one edge at a time

1. Pose one stumble = one edge, grounded concretely (real numbers, a specific case) so
   the learner can take a first step, then halt. Don't prefill their answer.
2. They commit. Diagnose against the sealed tree.
   - On target → confirm, name the concept the tree gives it, advance.
   - Divergent → invariant #2: reason for the divergence only, salvage what was right,
     re-pose the same edge. Loop until they reach it.
3. When they reach it, capture what the *specific* divergence revealed as a card
   (`card-add --slug <s>`) — the misconception they actually hit (e.g. "reversed the
   arrow: price→utility instead of utility→willingness-to-pay"), which the from-tree
   `card-draft` deck wouldn't contain. A miss is the trigger for card capture, never a
   verdict (hard rule #2): "the tree says X, your answer didn't reach X yet → here's a
   card," never "you got it wrong."

## Calibration

Productive failure is expensive; spend it where it pays.

- Full depth on `fan` edges (an assumption is dropped) and `join` edges (a benchmark
  is assembled) — where understanding is actually built.
- Light and fast on review nodes and `flow` chains that mirror an already-discovered
  structure (supply mirrors demand; a local-patch chain follows once the learner is on
  the rails). Pose it, let them spot the isomorphism, move on.
- Set each question where the learner can step once with the tools in hand but stalls
  at the key move. Too low = they read off the answer; too high = no foothold. Adjust
  per the previous answer.

## Faithfulness and scope

Judge only against the sealed tree; add nothing beyond it (narrative tree = working
hypothesis, hard rule #5; verify against `sources/` only if the learner doubts it).
When the learner raises a genuine concern the tree doesn't address, don't fabricate a
resolution: name it as real, say which later node resolves it, and park it. Early
skepticism is often exactly the obstacle a downstream node exists to remove — flag the
forward link.

## Hand-off

Discovery acquires; it doesn't consolidate. Once a tree (or a stretch of the DAG) is
reconstructed:
- `card-draft <slug>` builds the durable deck; the misconception cards minted here ride
  in it. Retention then lives in the Anki SRS, not chat.
- A node with real algebra → `derivation-scan` / `derivation-draft`, then the faded
  derivation drill for procedural mastery.
