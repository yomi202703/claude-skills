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
2. On a wrong/partial answer, split it. Affirm exactly the part that is genuinely
   correct — only that part, no charitable inflation beyond what they actually
   committed. Then refute the wrong part by reasoning: drive the logical negation of
   why that path fails, step by step. Both stay backward-looking, about the path they
   committed — refutation dismantles their move, it never hands the correct answer or a
   forward pointer (the next move, the tool to use, where to look). Re-pose the same
   edge. Closing the last gap is the learner's job — this is what separates discovery
   from lecturing.

   Bound the refutation's material: use only the learner's prior commits and the
   problem statement. "Refute by reasoning" otherwise reads as license to walk the
   solution out — and a leak through this channel doesn't feel like handing the answer,
   but is. Allowed: expose a contradiction between two things they already said, or with
   the given conditions; "that conclusion isn't supported yet"; re-pose the edge.
   Forbidden (these are the answer): computing a not-yet-stated value; naming the next
   unit/equation/graph-position to look at; a new decomposition; "first…", "if you look
   at…"; a concept the learner hasn't named. A contradiction inside their own words
   leaks nothing — prefer it. (Learner: "gain needs price below 199" after committing
   "buys 2 at 200" → refute by that contradiction, never by computing the first unit's
   250.)
3. A non-answer is not a commit — halt it, don't refute it. Three answer-states, not
   two: on-target, divergent (#2), and non-commit — an answer that decides nothing yet
   poses as one. There is no committed path to refute, so #2 does not apply; do not
   split-and-refute a lid as if it were divergent. Catch two lids:
   - Omnibus / invincible words — terms that would fit any outcome equally ("複雑だから",
     "バランスが大事", "中立", "不完全", "均衡点", "どちらも", "多角的に"). Surviving
     every case, they choose nothing.
   - Procedure words — answering with the procedure instead of its content ("流れで",
     "手順通り", "〜にしたがって"). Naming the steps is not taking one.
   On either, stop immediately and force a single concrete scene: re-pose the same edge
   for one specific case (real numbers, one named instance) and make the learner answer
   that. This leaks nothing — they produce the scene, you don't, so the value stays
   theirs (compatible with the leak discipline below).

   Exception — lid vs. breakthrough. When the learner drops explanation and bares a raw
   demand, question, or cry, that may be the abstraction pierced, not a lid. Default to
   lid (under-help, #4): treat it as a non-commit and force the concrete scene. Ride it
   forward as a breakthrough — carry the momentum straight to the next edge — only when
   it is unmistakably the demand the abstraction was hiding, never an evasion dressed as
   one.
4. Hints are pull, never push. Add scaffold only when the learner asks ("ヒント"), one
   notch at a time; raise the fade back once they recover. Never volunteer it. When
   unsure, give less and wait — silence is allowed. Default to under-helping.

Before sending any diagnosis, leak-check the finished draft (more reliable than
restraint mid-generation) and cut any sentence carrying: (a) a value not already stated
by the learner or the problem; (b) a pointer to where to look next. When in doubt, cut.

## The DAG generates the questions

Traverse `maps/<subject>-dag.json` in topological order, never ahead of a node's
parents (`ai_usage`: confirm parents first, then work from `desc` + the `trees` it
points to; add nothing the trees don't contain). Each edge is one stumble question;
its `kind` fixes the type:

- `flow` — stand the learner at the parent with only the parent's tools, pose the gap
  that forces the child. ("Given p=MC for a price-taker — now the firm can set
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
   - On target → confirm the logic. Then, before naming it yourself, pose the term as
     its own retrieval: "正解。ではこれは何と呼ぶ?" If they produce the canonical name,
     name-check and advance. If they can't (or name it wrong), that is a naming gap, not
     a divergence — give the term, then capture it (step 3). Don't reveal the term
     unprompted; encountered once, it is lost.
   - Divergent → invariant #2: affirm exactly the correct part, then refute the wrong
     part by reasoning, re-pose the same edge. Loop until they reach it.
   - Non-commit (an omnibus/procedure-word lid, not a divergence) → invariant #3: halt,
     force one concrete scene, re-pose the same edge. Don't refute — there is no
     committed path yet. (First rule out the breakthrough case before forcing the scene.)
3. Capture what the turn revealed as a card (`card-add --slug <s>`) — two triggers, both
   captures and never verdicts (hard rule #2), both for what the from-tree `card-draft`
   deck wouldn't reliably contain:
   - Misconception (from a divergence): the specific wrong turn they hit (e.g.
     "reversed the arrow: price→utility instead of utility→willingness-to-pay").
   - Naming gap (from a correct-but-unnamed answer): front = the role / problem-
     resolution they just reconstructed in their own words, back = the canonical term;
     add the reverse card (term → the problem it resolves) when the name alone is worth
     recall. card-draft wouldn't mint this — the term sits below node granularity.
   Framing for both: "the tree says X / calls it X, your answer didn't reach it yet →
   here's a card," never "you got it wrong."

## Calibration

The job is to protect the learner's next unaided commit, not to move them toward the
answer; closing the gap in one turn is the failure mode. The loop is many cheap turns.
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
