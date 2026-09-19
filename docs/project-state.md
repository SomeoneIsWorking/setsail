# setsail — project state

Factual capability inventory for Wind Waker HD on Linux. Epic intent is in
`docs/project-goals.md`. Every item is `verified`, `partial`, `blocked`, or `missing`.

**Current focus.** ST-BOOT — reach in-game control from the player's WUX through a
source-built runtime, so render-state RE can begin against a running game.

## Comparison baseline

**Baseline: playing Wind Waker HD in upstream Cemu.** A player installs the Cemu
AppImage, adds their WUX to a game list, optionally installs community graphic packs
(`WindWakerHD_Resolution`, `_Contrasty`, `_Shadows`, `_NoSSAO`, `_LODBias`,
`_Anisotropic`, `_RemoveHUD`, `_PictoBox`, `_IntelFixes`, `_FPSSlowdownFix`), and plays
at the title's 30 Hz presentation rate. No 60 fps pack exists for this title. Each item
below states its difference from that baseline.

| ID | Capability (delta from baseline) | State | Evidence / exact gap |
|---|---|---|---|
| ST-BOOT | Title boots to in-game control through our source-built runtime | missing | Blocked on `wiiuport` ST-BUILD. Same behaviour as baseline once it lands; it is the precondition for everything below. |
| ST-IDENT | Title identity is validated from the player's file before it is accepted | missing | The exact revision and its identity check are not yet recovered from the player's WUX. |
| ST-CAMERA | Camera transform recovered from the guest's submitted render state | partial | Slot inventory and candidates in `docs/render-state.md`: `offset=28` (4x4) paired with `offset=12` (3x4), written together from 3 source buffers. Gap: no values captured yet, so nothing is identified. Needs a driven run that holds the camera still and then moves only the camera. |
| ST-ACTORS | Actor/object transforms recovered, with identity stable across ticks | missing | Depends on ST-CAMERA. Unmatched objects must be counted and presented un-blended. |
| ST-60 | Presents at 60 Hz with interpolated frames from blended transforms | missing | Depends on `wiiuport` ST-REPLAY and ST-NULLDIFF, plus ST-CAMERA and ST-ACTORS. The headline delta from baseline. |
| ST-60-EVIDENCE | Interpolation proven by counters with denominators and code-diffed captures | missing | A run where interpolation never fired must fail, not pass quietly. |
| ST-PERF | 60 Hz sustained, frame-time percentiles published with the tested hardware | missing | No measurement exists. A 30 Hz-capable machine is not evidence for 60 Hz. |
| ST-SAVES | Saves and settings in the OS user-data location, not the checkout | missing | Baseline Cemu already uses `~/.local/share/Cemu`; our runtime must resolve its own XDG location rather than inheriting a checkout-relative path. |
| ST-SETUP | No-terminal first-run setup with a native picker for the player's disc image | missing | Must consume `shared/setup-ui`; no title-local picker. Baseline requires the player to configure Cemu manually. |
| ST-APPIMAGE | Asset-free Linux AppImage release | missing | |
| ST-RUNSH | `./run.sh` provisions from a clean checkout and launches the title | missing | |
| ST-VERIFIER | Canonical Python verifier with format, tidy, structure, and test gates | missing | |

## Dependencies

`wiiuport` owns the runtime and the title-neutral record/replace/replay mechanism.
This project owns only Wind Waker HD's identity, which submitted state is a camera or an
actor transform, the blend policy, packaging, and the release evidence.
