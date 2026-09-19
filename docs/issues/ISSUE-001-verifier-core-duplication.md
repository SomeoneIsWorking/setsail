# ISSUE-001 — Verifier gate core is duplicated between setsail and wiiuport

**State:** open. **Affects:** ST-VERIFIER (setsail), ST-VERIFIER (wiiuport).

`setsail/tools/setsail/verify.py` and `wiiuport/tools/wiiuport/verify.py` each define their
own `GateResult`, source-size limits, and gate runner with the same semantics. That is
one rule with two implementations, and they will drift.

**Why it was not shared immediately.** The two verifiers' *gates* already differ —
wiiuport gates a vendored upstream build tree and excludes it from formatting and size
limits, setsail gates the launcher shim and will gate packaging. Only the runner and the
size-limit policy are genuinely the same rule. Extracting a shared repository for that
much is an architecture decision larger than the change that surfaced it, and setsail
depending on wiiuport's *maintainer tooling* would be the wrong dependency direction:
setsail consumes wiiuport's runtime, not its build policy.

**What resolves it.** Extract `GateResult`, the gate runner, and the source-size policy
into one owner the moment either of these happens, whichever comes first:

- a third project in this family needs the same gates, or
- the two copies' size-limit policy diverges for any reason other than a deliberate,
  documented difference.

Until then the duplication is bounded to two files and is recorded here rather than
being discovered later as drift.
