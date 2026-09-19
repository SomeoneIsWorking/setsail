# setsail — project goals

Wind Waker HD on Linux desktop, presenting at 60 Hz by interpolating the game's own
render state. Epic intent only; capability status lives in `docs/project-state.md`.

Active title: **The Legend of Zelda: The Wind Waker HD (USA) (En,Fr,Es)**, supplied by
the player as a WUX disc image. The title is the single conformance target.

## GOAL-PLAY — The player's own copy boots and plays

**Outcome.** From a clean checkout, `./run.sh` provisions everything portable, builds the
runtime, and launches Wind Waker HD from the player's own game files at full speed with
working video, audio, input, and saves.

**Why.** Everything else in this project is measured against a running game.

**Success conditions.**
- Boot from the player's WUX to in-game control, no terminal steps.
- Saves and settings persist in the OS user-data location, never in the checkout.

**Constraints.** The disc image, its keys, and anything derived from them are the
player's. They never enter the repository, CI, a commit, a package, or a hosted secret.

**Non-goals.** Supporting other Wii U titles. Being a general-purpose emulator UI.

## GOAL-60 — True 60 Hz presentation by interpolating recovered render state

**Outcome.** Wind Waker HD simulates at its own 30 Hz and presents at 60 Hz. The extra
frames are real rendered frames: the runtime replays the frame's draw stream with camera
and actor transforms blended between the previous and current simulation tick. Geometry,
topology, UVs, depth, and materials come from the game's own submitted state.

**Why.** The simulation is 30 Hz-locked; there is no working community 60 fps pack for
this title precisely because raising the tick rate breaks it. Interpolating the
transforms the game already submits raises presentation rate without touching
simulation semantics.

**Success conditions.**
- The camera transform source is identified in the guest's submitted render state, with
  evidence tying the recovered slot to observed camera motion — not inferred from pixels.
- Actor/object transforms are identified and blended per object, with stable identity
  across ticks so an object is never blended against a different object's state.
- A held-still scene produces an interpolated frame byte-identical to its neighbours.
- A moving scene shows the interpolated frame strictly between its neighbours, verified
  by code against the two source transforms, not by eye.
- Objects whose transform cannot be matched across ticks are presented un-blended rather
  than blended against the wrong state, and are counted.

**Constraints.** Deterministic and source-state-driven. No image-space motion
estimation, no reading back rendered pixels to decide geometry, no content-dependent
sampling. Every blended value has explicit provenance.

**Non-goals.** Changing the game's tick rate. Image-space frame generation.

## GOAL-EVIDENCE — Interpolation is proven, not asserted

**Outcome.** The claim "interpolated 60 fps" rests on counters with denominators and on
captured frames diffed by code, produced by a headless maintainer run that never seizes
the desktop.

**Success conditions.**
- A run reports: simulation ticks, presented frames, interpolated frames, replay
  bailouts by reason, transform slots blended, and objects presented un-blended.
- A run in which interpolation never fired fails the gate rather than passing quietly.
- Frame-time percentiles at 60 Hz on the tested machine, published with the hardware.

## GOAL-SHIP — A no-terminal Linux release

**Outcome.** A Linux AppImage that shows a first-run setup screen asking for the
player's Wind Waker HD disc image with a native file picker, validates the selection
against the title's identity before accepting it, and persists it with the platform's
user-configuration API.

**Constraints.** The package is asset-free. Environment variables and command-line paths
remain maintainer overrides, never player prerequisites.
