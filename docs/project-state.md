# setsail — project state

Factual capability inventory for Wind Waker HD on Linux. Epic intent is in
`docs/project-goals.md`. Every item is `verified`, `partial`, `blocked`, or `missing`.

**Current focus.** ST-60 -- the objects three frames cannot verify, and the uneven halves of a tick
(ST-PERF). The work is in `wiiuport`; this inventory points at its evidence.

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
| ST-ACTORS | Actor transforms recovered with stable identity across ticks | partial | The title double-buffers its uniform blocks, so a draw's shader and block addresses identify an object two frames apart; `wiiuport`'s `interp::ObjectPlanner` pairs each object with its draw one frame back by where its own moved values pass through, finding it by values where the blocks name another object, and treats values every draw of a shader holds -- the view -- as frame state rather than identity. Evidence and gaps: `wiiuport` ST-OBJECTS. |
| ST-60 | Presents at 60 Hz with interpolated frames from blended transforms | partial | The runtime presents an in-between frame before every guest swap with the camera and each object blended by its own identity; state and evidence live in `wiiuport` ST-60 and ST-OBJECTS. Live, walking: 792 in-between frames for 798 title frames, the title keeping 98.3% of its rate over paired windows. Gaps are listed there: objects whose identity three frames cannot verify (5.6% of a census, mostly the sea grid's edge coming into view) are drawn un-blended and counted; the HUD is keyed by draw order; effects drawn without uniform blocks are not blended. |
| ST-60-EVIDENCE | Interpolation proven by counters with denominators and code-diffed captures | partial | `wiiuport`'s `tools/continuous_run.py` reports ticks, in-between frames, skips by reason, objects by outcome and by shader, and fails a run where interpolation never fired (`wiiuport` ST-COUNTERS). The between check is on the values drawn; no capture of an in-between frame is yet compared by code with its neighbours' images. |
| ST-PERF | 60 Hz sustained, frame-time percentiles published with the tested hardware | partial | Measured walking with interpolation on (`wiiuport` `tools/continuous_run.py`): frame time p50 16.7 ms, p95 30.3 ms, p99 35.8 ms over 1,589 intervals -- not sustained, since the halves of a tick are uneven (median 21.9 ms title-to-in-between, 13.2 ms back). The tested hardware is not yet published with it. |
| ST-SAVES | Saves and settings in the OS user-data location, not the checkout | missing | Baseline Cemu already uses `~/.local/share/Cemu`; our runtime must resolve its own XDG location rather than inheriting a checkout-relative path. |
| ST-SETUP | No-terminal first-run setup with a native picker for the player's disc image | missing | Must consume `shared/setup-ui`; no title-local picker. Baseline requires the player to configure Cemu manually. |
| ST-APPIMAGE | Asset-free Linux AppImage release | missing | |
| ST-RUNSH | `./run.sh` provisions from a clean checkout and launches the title | missing | |
| ST-VERIFIER | Canonical Python verifier with format, tidy, structure, and test gates | missing | |

## Dependencies

`wiiuport` owns the runtime and the title-neutral record/replace/replay mechanism.
This project owns only Wind Waker HD's identity, which submitted state is a camera or an
actor transform, the blend policy, packaging, and the release evidence.
