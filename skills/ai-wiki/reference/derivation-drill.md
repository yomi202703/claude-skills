# Derivation drill (chat-time behavior) — faded, procedural

Read this when the user asks to be drilled on a **derivation** (a
`derivations/<slug>.md` spine), not on declarative content. Declarative knowledge
("can you say X?") and procedural knowledge ("can you *derive* X?") are different
skills; cards train the former, this drill trains the latter. The proven shape is
**worked → faded → independent** (faded worked examples) over a subgoal-labeled
spine. The spine (`## SPINE`, the `[⇣n]` chain) is the single source of truth.

Conducted by you in chat; there is no `dispatcher.py` command and no `.tsv` — the
durable artifact is the spine itself (a verified spine can be Anki-carded later via
`card-draft` once transfer has happened).

## Loop — one step at a time, plus a fade ladder

1. Show the **GOAL** and the **subgoal map** (the `[⇣n]` labels only, not their
   content). The labels are the scaffold — subgoal labeling is what transfers.
2. Reveal steps already established; ask for **one** next step's actual math. Tell
   them to do it on paper first. Halt. Never pre-fill their work.
3. Compare their step against that `[⇣n]`'s content in the spine. If it reaches the
   spine, reveal it and advance. If it doesn't, that is **not** a verdict on them
   (hard rule #2) — it is only the trigger to **drop that step's fade one notch**
   next round (show more scaffold) and to note it for re-drilling. Say "the spine's
   ⇣k is …, your step didn't reach it yet — let's fade less here," never "wrong."
4. Fade ladder across repetitions of the same derivation: **F0** all steps shown
   (read it) → **F1** last step hidden → **F2** back half hidden → **F3** only the
   GOAL given, reproduce the whole chain. Raise the fade as they succeed, lower it
   on a miss.

A step marked `[~]` in the spine is **unverified** (the source skipped it and the
judge couldn't confirm). Flag that when you reach it — drill it, but tell the user
to check it against the source/instructor; don't present it as settled.
