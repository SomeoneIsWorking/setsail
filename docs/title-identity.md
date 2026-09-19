# setsail — title identity

The single conformance target. Anything that must recognise the player's files reads
these facts from here; they are not duplicated into code as bare literals.

| Field | Value | Source |
|---|---|---|
| Title | THE LEGEND OF ZELDA The Wind Waker HD | Title metadata |
| Title ID | `0005000010143500` | Title metadata |
| Group ID | `00001435` | Title metadata |
| Title version | `0` (no update installed on the tested copy) | Title metadata |
| SDK version | `20911` | Title metadata |
| Region | `2` (USA; En, Fr, Es) | Title metadata |
| App type | `80000000` | Title metadata |
| Container format | WUX (compressed, deduplicated WUD disc image) | File extension and container header |

**How these were obtained.** Read from the baseline emulator's own parsed title cache
(`~/.local/share/Cemu/title_list_cache.xml`) for the tested copy of the disc image. That
is the baseline's parse of the player's file, which is adequate to name the target but is
**not** an identity check we can ship: it is a third-party cache, not a validation we
perform. `ST-IDENT` stays `missing` until setsail parses the identity out of a supplied
file itself and rejects a non-matching one. The pinned runtime can already read
`meta/meta.xml` out of a WUX, which is the intended source for that check.

**Player file location.** The disc image is the player's and lives outside this
repository. Its path is configuration supplied at first run, never a tracked constant,
and no path to it is recorded in this repository.

## Recovered runtime facts

Facts about how this title behaves at runtime, each with how it was measured.

| Fact | Value | How it was measured |
|---|---|---|
| Presentation cadence | `GX2SetSwapInterval(2)` — the title flips on every second vsync, so it presents at 30 Hz on a 60 Hz cadence with every second flip repeating the previous image | Driven offscreen run of the baseline emulator against the player's disc image with GX2 logging enabled; exactly one matching line across the full 791,368-line log, on 2026-09-19 |

This is the fact that makes interpolation fit the existing timing rather than adding
presents; the mechanism consequence is worked out in wiiuport's
`docs/issues/ISSUE-003-wwhd-swap-interval.md`.

**Not yet established:** that the title's simulation advances exactly once per flip. The
swap interval says how often it presents, not how often it steps. A blend phase of 0.5
is unjustified until that is measured, and `ST-60` must not assume it.

**A second copy of this title is not a second target.** A different region, revision, or
an installed update is a different conformance target and needs its own recovered
identity before it is claimed to work.
