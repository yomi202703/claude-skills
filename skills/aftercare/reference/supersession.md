# supersession pass (residue)

Loaded by aftercare for the supersession pass, on the git scope the router hands it. Find what still assumes a superseded world, classify how to treat it, then act only where the current truth is unambiguous. The evidence model is "it points at a world that no longer exists" — the inverse of reachability's "nothing references it".

Lenses (collect candidates):

- Dangling reference: a registration, link, import, or path pointing at something that was deleted.
- Git deletion or rename still grepped live: history removed or renamed X, and grep still finds the old form.
- Version-duplicate or deprecation marker: `foo_old`, `v2`, commented-out blocks, 旧 / deprecated / `TODO(remove)`.
- Ledger-staleness signature: STATUS older than the latest decision; a completed item still in TODO Active; a decision reversed by a later one whose artifact still exists.

Governance mask (apply before deciding which side is the old one; the repo's four-role docs):

- `archive/` is out of scope — frozen-old by design.
- A decisions entry is never a deletion target — the ledger is append-only; the residue is the artifact an old decision produced (old code or file), not the entry text.
- A stale STATUS is rewritten to current, never deleted.
- A completed-but-Active TODO item moves to decisions; a Deferred item with no unblock trigger is surfaced as a governance smell.

Four-way classification (every candidate gets one before any action):

- delete — no current use and no preserved value.
- rewrite — a current-snapshot doc (STATUS, README) describing an old world: update it to current.
- redirect — a live reference to a renamed or moved target: re-point it to the new side.
- preserve — old but load-bearing: a compat alias, migration shim, old API / CLI / env name, negative or regression test, golden file or fixture, changelog, or anything an external consumer reads. Never auto-delete these.

Truth-oracle gate (decide which side is current; runs parallel to the reachability pass's proof):

- Name the concrete new side that superseded the candidate. If none can be named, it is not supersession residue — leave it, or hand a pure orphan to the reachability pass.
- Confirm the new side is current via executed / entrypoint-reachable code (strongest for behavior), the latest decisions entry, or the git scope the router handed in.
- Warm path: when that git scope shows the candidate was just superseded, act without waiting for full oracle agreement — but only on a candidate that already survived the four-way classification, so preserve / redirect / rewrite are carved out first. A live consumer still present means incomplete removal (breakage), not residue: surface it, do not clean it.
- Cold path (old accumulated residue, not in this scope): act only when the new side is named, a strong oracle confirms it current, no oracle contradicts, and the governance mask passed. Otherwise present, do not act.
- Invariant: never remove anything an oracle proves is currently load-bearing, however old it looks. An oracle conflict (code does B, the latest decision says A) is itself a finding — surface it, do not auto-resolve.

Live use is wider than AST references: string literals, prompt and markdown mentions, glob or convention-based loading, shell / CI / manifest paths, and cross-repo use all count. Failing to prove use is not proof of residue.
