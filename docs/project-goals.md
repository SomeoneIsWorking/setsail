# setsail — project goals

Wind Waker HD on Linux desktop, presenting at 60 Hz by interpolating the game's own
render state. Epic intent only; capability status lives in `docs/project-state.md`.

**Where this title's half of the work lives.** The addresses, the stand-in's words, the
blend policy and the evidence are this project's, in `docs/render-state.md`. The runtime it
launches owns only the title-neutral capabilities those need -- writing the guest's own
memory, and the emulator's flip pacing -- and says what each one is. That split is a
statement of fact about where the code is today, not a claim that the boundaries are
finished: `setsail` has no C++ build of its own, so the title's module currently compiles
inside the runtime it provisions. The intent is that it does not.

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
frames are real rendered frames, drawn by the title's own render path with the pose blended
between the previous and current simulation tick. Geometry, topology, UVs, depth,
skinning and materials are the title's own: it draws the blended frame itself, at a pose
the blend put in the uniform block the title's own binder is about to bind. The simulation
rate is untouched -- the picture's rate comes from the flip.

**Why.** The simulation is 30 Hz-locked; there is no working community 60 fps pack for
this title precisely because raising the tick rate breaks it. Interpolating the
transforms the game already submits raises presentation rate without touching
simulation semantics.

**Success conditions.**
- The pose is located in the title's own state, with the addresses it was read from, and
  not inferred from pixels or from a statistical search for something that moves.
- Each object's identity is the title's own -- the node whose draw binds the block -- so
  an object is never blended against a different object's state.
- The previous tick's block is still present when this tick paints, measured rather than
  assumed, since that is what a blend of the two needs.
- The title presents at 60 Hz with its logic rate unchanged, both measured on the real
  title in a headless run with denominators.
- The null case is measured too: two paints with no substitution are byte-identical, and
  the blended paint differs from both, nearer each than they are to each other.

**Constraints.** Deterministic and source-state-driven. No image-space motion
estimation, no reading back rendered pixels to decide geometry, no content-dependent
sampling. Every blended value has explicit provenance.

**Non-goals.** Changing the game's tick rate. Image-space frame generation. The
non-goal is about the *rate*, and the mechanism does not touch it: the picture's rate
comes from the flip and the logic keeps its own. What it does change is named here
rather than left to be discovered, and the list is exhaustive of what a stand-in in
the display path touches:

- one word of a vtable the display thread already calls, so the display thread paints
  through the stand-in;
- **the first word of the display frame itself**, replaced by a relative branch into a
  stub the runtime allocated, with the title's own instruction preserved inside that
  stub and executed there before the frame resumes. This is a change to the guest's
  *code*, not to a pointer to it;
- **executable memory in the loader's trampoline area**, allocated through the loader's
  own allocator, which holds the stand-in's payload and the stubs. That area's base is
  the HLE registry's code, then its symbol names, then zero padding, so a branch that
  lands in it executes data as code -- which is the fault this project is chasing;
- the title's own record of the interval it asked for;
- the emulator's flip pacing;
- and a gate in the logic path, which is a **backstop and not this project's finding**.
  The measurement says the logic is *not* slaved to the flip: with the stand-in painting
  at 59.99 and 60.12 a second the logic read 30.12 in both windows, and the tick runs once
  per paint in the unmodded title because that is what the title does. The gate exists so
  that a title which *is* slaved has somewhere to be held, and its shape, its counters
  and what it does to the simulation are title policy, in `docs/render-state.md`.

**Ownership.** The emulator-side capability — writing into guest code space, reading and
writing guest words in the guest's own order, invalidating what was compiled over them,
and setting the flip pacing — is title-neutral and belongs to the port, which offers it
without knowing any title. Everything that names *this* title is this project's: the
addresses, the payloads, which of the three effects a given presentation mode needs, the
ring of per-object uniform blocks, and the decision to lerp N-1 into N. The title project
is not a C++ project, so the code that carries those addresses is written in the port's
`title` namespace rather than here; what is kept here is the evidence they rest on and
the decision they encode, and the port's `docs/project-state.md` reports what was
measured. A payload whose word came from a statistical search rather than from the
title's image does not belong to either, and is not to be written.

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
