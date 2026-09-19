# setsail — project state

Factual capability inventory for Wind Waker HD on Linux. Epic intent is in
`docs/project-goals.md`. Every item is `verified`, `partial`, `blocked`, or `missing`.

**Current focus.** ST-ACTORS — identify actor transforms by value and give them
identity that survives a tick, which is the remaining unknown before a blend can be
written. ST-CAMERA is settled.

## Comparison baseline

**Baseline: playing Wind Waker HD in upstream Cemu.** A player installs the Cemu
AppImage, adds their WUX to a game list, optionally installs community graphic packs
(`WindWakerHD_Resolution`, `_Contrasty`, `_Shadows`, `_NoSSAO`, `_LODBias`,
`_Anisotropic`, `_RemoveHUD`, `_PictoBox`, `_IntelFixes`, `_FPSSlowdownFix`), and plays
at the title's 30 Hz presentation rate. No 60 fps pack exists for this title. Each item
below states its difference from that baseline.

| ID | Capability (delta from baseline) | State | Evidence / exact gap |
|---|---|---|---|
| ST-BOOT | Title boots to in-game control through our source-built runtime | partial | The title boots and draws a scene through our fork, and render-state RE is running against it: a capture at frame 300 yielded 6026 draws across 194 shaders. That binary is built by CI, not locally, so the source-built claim is unproven on a developer machine while `wiiuport` ST-BUILD stays blocked. In-game control has not been reached either: no input is driven, so only the unattended opening scene has been seen. |
| ST-IDENT | Title identity is validated from the player's file before it is accepted | missing | The exact revision and its identity check are not yet recovered from the player's WUX. |
| ST-CAMERA | Camera transform recovered from the guest's submitted render state | verified | Identified by value in `docs/render-state.md`: a 3x4 (3x3 rotation, translation in the fourth column) carried by 71 of 194 shaders in one frame, each at its own offset. Row norms 1.00000, row dot products 1e-8, constant across every draw of a frame in shaders drawn up to 123 times, translation moving ~2140 units/frame with under 2% step variation. Sharing across unrelated shaders is the discriminator; the other two properties alone do not separate a camera from a moving object. Found by `wiiuport/tools/find_camera.py` from a capture at frame 300. Bounded by one scene and four frames, with no input driven -- offsets are per-shader and must be found at runtime, never read from a table. |
| ST-ACTORS | Actor transforms recovered with stable identity across ticks | partial | Moving actor transforms are located by value (31 distinct orthonormal 3x4s across 93 draws of one shader, changing every frame). Identity now has a measured basis rather than a heuristic: the capture records each draw's guest uniform block address, and the title double-buffers them -- 153 of 153 keys in one shader appear at a single frame parity, with frame sets exactly [0,2,4,6], and 1700 of 1738 across all shaders. Two approaches are ruled out by measurement: draw-index matching (28x worse than nearest neighbour) and nearest neighbour itself (silently swaps identity when actors pass close). Exact gap: the address links frame N to N+2, while an interpolated frame sits between N and N+1, so the pairing of each object's two alternating addresses still has to be established and verified. 38 non-single-parity keys are unexplained. |
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
