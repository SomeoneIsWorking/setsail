# Wind Waker HD render state: what is known, and how

Which of the title's submitted values are transforms, and which of those are the camera.
This is the input to the blend policy. Nothing here is an identification until it has a
measurement behind it; candidates are labelled as candidates.

## Where the title's transforms can live

Measured, not assumed: the title uses **both** Latte uniform paths heavily
(`GX2SetVertexUniformReg` 70,752 calls, `GX2SetVertexUniformBlock` 20,529 — see
`docs/title-identity.md`). Anything that reads only one of them sees part of the state.

## Uniform-register slot inventory

From the same driven offscreen run, parsing every
`GX2SetVertexUniformReg(offset, count, sourcePointer)`. Offsets and counts are in
32-bit words, so `count == 16` is a 4x4 matrix and `count == 12` a 3x4 affine one.

Shape totals across 70,752 calls:

| count | calls | reading |
|---|---|---|
| 4 | 54,308 | single `vec4` — colours, parameters, packed scalars |
| 16 | 12,298 | 4x4 matrix |
| 12 | 4,146 | 3x4 affine matrix |

The matrix-shaped slots, by volume:

| offset | count | calls | distinct source buffers |
|---|---|---|---|
| 0 | 16 | 2,809 | 22 |
| 28 | 16 | 2,536 | 3 |
| 32 | 16 | 1,104 | 2 |
| 76 | 16 | 1,077 | 8 |
| 100 | 16 | 951 | 6 |
| 64 | 16 | 654 | 8 |
| 12 | 12 | 2,536 | 3 |
| 16 | 12 | 1,104 | 2 |

## Uniform-block inventory

`GX2SetVertexUniformBlock(location, sizeInBytes, sourcePointer)`, all 20,529 calls from
the same run. The title binds blocks at **only four locations**:

| location | size | calls | distinct source buffers | floats |
|---|---|---|---|---|
| 4 | 768 B | 12,510 | 58 | 192 |
| 2 | 512 B | 2,424 | 26 | 128 |
| 3 | 672 B | 2,121 | 2 | 168 |
| 1 | 64 B | 1,221 | 16 | 16 |
| 1 | 256 B | 1,050 | 14 | 64 |
| 4 | 1024 B | 1,050 | 14 | 256 |
| 1 | 768 B | 153 | 2 | 192 |

Two readings worth testing:

- **Location 3, 672 bytes, 2 distinct buffers** repeats the `offset=28` signature: heavy
  traffic out of a tiny fixed set of engine-owned buffers. 168 floats is exactly 14 3x4
  matrices, though it is equally divisible other ways, and a per-frame constant block of
  lighting and fog would look the same from here.
- **Location 4, 768 bytes, 58 distinct buffers** is the opposite signature and the
  natural place to look for **actor** transforms (ST-ACTORS). 192 floats is 16 3x4
  matrices, the shape of a skinning palette, which would make each bound buffer one
  animated character.

Neither is established. Both are shapes.

## The camera, measured

The view transform is **twelve consecutive floats: a 3x3 rotation with translation in
the fourth column, stored as three rows of four.** It is written into the assembled
uniform buffer of 71 of the 194 shaders drawing one frame, each at its own float
offset — 12, 16, 20, 28 and 32 all occur.

Three properties were measured together, and it is the third that identifies it:

| property | measured | why it matters |
|---|---|---|
| constant within a frame | identical across all draws of a frame, in shaders drawn up to 123 times per frame | an object transform is not |
| a real rotation | row norms 1.00000, row dot products at 1e-8 | rules out colours, fog terms and projection rows that happen to hold still |
| shared between shaders | the same twelve floats in 71 of 194 shaders in one frame | **the discriminator.** An object's transform reaches only the shaders drawing that object; every pass drawing the world is handed the same view |

Neither of the first two alone decides anything. A moving object drawn by one shader
satisfies both.

Across four consecutive frames its translation moved by 2160.6, 2135.5 and 2114.3 units
— under 2% variation between consecutive steps. That smoothness is the property
interpolation depends on, and it was measured rather than assumed.

The rotation is orthonormal to 1e-8, so interpolating it elementwise is wrong in
principle even where it is numerically close; it needs to be interpolated as a rotation.
Translation lerps directly.

## Two further shared transforms, not yet identified

The same test finds two more transforms in the same frame, recorded here so they are not
rediscovered:

- **30 shaders, translation (-194587.8, 3581.6, 319778.5), moving 0.1 units per frame.**
  Shared widely enough to be engine-owned, but nearly static while the camera moves fast.
- **23 shaders, rotation-only, translation exactly zero.** Consistent with the view's
  rotation without its translation, which is what a skybox or a normal transform needs.

Both are hypotheses about what they are. Their measured properties are not.

## How this relates to the call-shape inventory above

It does not line up, and the offsets are not comparable. The inventory above was built
from GX2 call logging, which sees `GX2SetVertexUniformReg` offsets in the guest's
register space. The capture reads the buffer the renderer assembles, whose offsets are
the shader's own layout. The camera-carrying shaders report `loc_uniformRegister = -1`
and `loc_remapped = 0`: they are driven through uniform blocks, not registers, so the
register inventory could not have seen them at all.

The earlier reading of that inventory — a 3x4 at `offset=12` paired with a 4x4 at
`offset=28`, inferred from equal call counts and few distinct source buffers — was a
hypothesis about a layout and is not what the values show. Equal call counts did not
mean what it assumed.

## Actors: what they look like, and why identity is still open

A capture at frame 900 (1,619 draws a frame, against 25 at frame 3000) holds moving
actor transforms. The same 3x4 shape, but differing between draws of one frame rather
than shared across the frame: in shader `b7252004aba21c10` at float offset 4, 31 distinct
orthonormal matrices across 93 draws, changing at every one of 7 frame boundaries.

The scene at frame 300 has none. Its five per-draw transforms are byte-identical across
all four frames — static scenery. A capture can therefore contain a perfectly good camera
and no actor motion at all, which is why actor work needs its own scene and cannot be
read off whichever capture proved the camera.

### Draw order is not an actor identity

The cheapest hypothesis is that the *n*th draw of a frame is the same object as the *n*th
draw of the next. It is wrong, and measurably so:

| pairing between consecutive frames | median | mean |
|---|---|---|
| same draw index | 0.00 | 296.00 |
| nearest neighbour in translation | 0.00 | **10.39** |
| random | 391.60 | 1152.99 |

Order-matching is 28x worse than nearest neighbour. The reason is visible in the draw
counts themselves, which fall 93, 87, 87, 81, 72, 72, 69, 69 across the eight captured
frames: objects enter and leave, so every index after a removal refers to something else.
Order-matching still beats random, which is exactly how this would pass a careless check.

Nearest neighbour is not the answer either. It is a heuristic that silently swaps identity
whenever two actors pass close, and a swapped identity produces a blend that interpolates
between two different objects — visible as an object jumping across the scene.

### The guest address identifies an object, but only every other frame

The capture now records the guest physical address of every uniform block a draw
sourced, taken from `LatteGPUState.contextRegister` where the engine's own loader reads
it. That address was expected to be the identity. It is, with a structure that has to be
respected:

**The title double-buffers its uniform storage.** Of 153 distinct address keys in one
shader across 8 captured frames, 120 appear in exactly four, and their frame sets are
exactly `[0, 2, 4, 6]`. Every one of the 153 appears at a single frame parity; across all
shaders, 1,700 of 1,738 multi-frame keys do. An object writes into one buffer on even
frames and another on odd.

So an address links frame *N* to *N+2*, not to *N+1* — and *N+1* is the interval an
interpolated frame sits in. Taken naively the address looks like a failed identity: no
key at all persists across every captured frame.

The identity of an object is therefore **the pair of addresses it alternates between**.
Establishing that pairing needs one cross-parity match, but unlike per-frame nearest
neighbour it is learned once and then checkable: a wrong pairing keeps producing a
discontinuity at every frame, which is detectable, where a per-frame heuristic fails
silently and only on the frames where two actors pass close.

The 38 keys that are not single-parity are not explained yet and are recorded so they are
not mistaken for noise later.

## The quad effects, recovered from the executable

The rings a swimmer or a boat leaves on the water and the sea's wave crests (vertex shader
`8cecd19741c6c1c7`) carry no identity in their vertices: each draw is one quad of four world-space positions with
the fixed UVs (0,0), (1,0), (1,1), (0,1). Their identity was recovered from `code/cking.rpx`
with the wiiuport maintainer tools (`wiiuport_title_files` extracts it, `rpx_to_elf.py`
links it for Ghidra), read against the GameCube decompilation (zeldaret/tww):

- `0x025a6c3c` is `dPa_ripplePcallBack::draw(JPABaseEmitter*, JPABaseParticle*)`, reached
  only through its vtable slot `0x100523c4` (vtable `0x10052398`, installed by
  `d_particle.cpp`'s static initialiser `0x025aa790`). It writes one particle's quad:
  20 floats, stride 20, each corner the particle's position plus its rotated half-extents,
  dropped onto the water height, then draws it with `GX2DrawIndexedEx` through `0x02825284`.
- Its third argument (`r5`) is the particle. The GameCube layout holds where HD's code
  reads it: `+0x28` `mGlobalPosition`, `+0x78` `mCurFrame` (the particle's age),
  `+0xc0` `mRotateAngle`. HD adds `+0xe0`: the particle's own vertex store, two buffers
  at `+0x000` and `+0x254` (each's first word the vertex bytes' guest address) chosen by
  the flip word at `+0x950`. That is why ring draws alternate between two buffers.

So a ring's identity is its particle's address, and a particle reborn in the same pool
slot is told from one that continues by its age. That `mCurFrame` restarts when JPA reuses the
particle is read from the decompilation (`JPABaseParticle::init*` sets it to 0), not yet measured live.

The ripple draw is one of the particle writers that end with one commit, `0x02825158`
(`commit(particle, store)`): it flushes the particle's written buffer (`store == 0`: the
store at `+0xe0`; otherwise a second store at `+0xe4`) and flips it. The ripple draw and
14 JPA draw executors (`0x02832b34`..`0x02835a20`, which billboard each corner through the
view matrix) call it. Live it runs about 13 times a tick, and `8cecd197` draws about 134
quads, so the particles are only a tenth of that shader.

The rest are the sea's wave crests: `drawWave` over `dKankyo_wave_Packet::mEff[]` in
`d_kankyo_rain.cpp`, HD's `0x02574d38`. Each wave `i` (stride `0x38` from packet `+0xa0`;
`+0x24` from there its counter, `sin` of which scales it and which only rises while the
wave lives) owns a vertex store at packet `+0x424c + i * 0x4c0`, two buffers of `0x254`
chosen by the flip at `+0x4a8`. The writer fills the quad, flushes it through the title's
vertex-buffer flush `0x027b5e94` (`flush(buffer, offset, size)`; the vertex bytes' guest
address at buffer `+0x140`) from `0x02575484`, and flips. At that call `r30` holds the
packet and `r23` the index. A wave that strays past the spawn radius is moved elsewhere in
its slot with its alpha set to 0 (`wave_move`), not reborn with a new counter.

The same flush has 66 call sites. `ca2d0854ee6b264d`'s quads are the sky's cloud cards:
`drawVrkumo` over `dKankyo_vrkumo_Packet::mInst[100]`, HD's `0x02575b6c`, reading the
packet at env light `+0xa94` (the GameCube's `mpVrkumoPacket` at `0xA14`; HD's fields sit
`0x80` past the GameCube's, the wave packet at `+0xaa0` against `0xA20`). HD draws two
groups of three layers of 100 cards, each card owning a buffer pair at packet
`+0x11dc + group * 0x574f8 + card * 0x4a8` (`0x254` apart), with one flip per group at
group `+0x574e0`. It flushes all 300 pairs of a group in one batch after drawing, from
`0x02576ff0` and `0x0257703c`; at each call `r31` holds the address of the group's flip, so
a card's first buffer is `r3 - flip * 0x254`. `vrkumo_move` moves a card that strays
past its radius elsewhere with its alpha at 0 rather than renewing it, so a card has no age.

`197fcd05d9572df3`'s 1.5 KB meshes are flushed by a shared double-buffer helper, `0x027ff1d8`, called from
`0x025ed1bc` (returning to `0x025edb2c`) and `0x025ec62c` (`0x025ed110`), which assert
`size_p != 0` in `m_Do_ext.cpp`: they are `mDoExt_3DlineMat*::update`, the 3D lines
(ropes and cords). Each line owns its vertex set, so a line's buffers are its identity,
and the shadow volumes `3ec2040d` and `ce43cd08` read the same buffers. At the helper's call
`r3` is the line's set: per list (count, first buffer) 8 bytes each, the flip at `+0x1c`,
buffers `0x250` apart with the vertex bytes' guest address at buffer `+0x148`; `r5` is how
many buffers it flushes. A line has no age, since it lives as long as what holds it.

## The frame loop, recovered from the executable

Measured with wiiuport's caller census (`WIIUPORT_CALLER_CENSUS`, `GET /callers`) in one
headless run: each function below ran exactly once per tick (2,771 calls over 2,769 ticks),
each from the one call site named.

The logic thread runs the GameCube's tick unchanged in shape. `fapGm_Execute` (`0x025d42ec`,
called from the main loop's body `0x025f172c`) calls `fpcM_Management(0, fapGm_After)`
(`0x025df948`, found by its `f_pc_manager.cpp` asserts), which runs every process's execute
(`fpcEx_Handler`, `0x025df5c0`), then every process's draw (`fpcDw_Handler`, `0x025de37c`,
with `fpcM_DrawIterater` `0x025df908`), then `fapGm_After` (`0x025d42c4`: scene, overlap and
camera management). The GameCube painted the previous tick's lists at the top of
`fpcM_Management` (`cAPIGph_Painter`); HD's call there is the rumble update (`0x025f2b08`)
instead, and HD's `g_cAPI_Interface` (`0x1018c498`) names `mDoGph_Create` `0x025f0550`,
before-of-draw `0x025f03c4` (resets the draw list at game info `+0x5d30`), after-of-draw
`0x025f03f0` (game info `+0x60ec`) and a painter `0x025f094c` that is `li r3,1; blr`.

HD paints on a display thread of its own: `0x0274c00c` calls its display's vtable slot `0xcc`
(`0x0274c264`, the frame) forever. The display (vtable `0x10004e88`) runs per frame: slot
`0xd4` `0x0274c67c` (begin), `0xdc` `0x02034ffc` (the title's override, which draws a tree of
render nodes through `0x02747c6c`/`0x02747bdc`, each node's draw through its own vtable),
`0x6c` `0x02747818` (a list of render objects), `0xec` `0x020350c4` (`GX2DrawDone`, the swap
`GX2SwapScanBuffers` in `0x0274c8c4`, ProcUI) and `0xe4` `0x0274c874` (`GX2WaitForVsync`).

So the title builds a tick's draw lists on its logic thread and paints them on the display
thread. A second paint per tick, of blended state, belongs on that thread; not yet known: how
the two threads hand a tick over, and where each model's matrices are when painted (J3D's
draw matrices are double-buffered on the GameCube, which would leave the previous tick's
beside this one's).

### The paint, read from the executable

Read on 2026-09-26 out of the title's own RPX, converted by `wiiuport`'s `rpx_to_elf.py`
and disassembled; every address below is that image's, so it is the address the running title
executes. This is the display thread's frame, `0x0274c264`, called through the display vtable
at `0x10004e88` (slot `0xc4` `0x0274c00c` is the thread entry, `0xcc` the frame). In order:

| step | code | what it does |
|---|---|---|
| begin | slot `0xd4` `0x0274c67c` | frame begin |
| the world's paint | slot `0xdc` `0x02034ffc` | takes the render tree at `display+0x1c`, asks its vtable `+0xc` whether it is drawn (`0x02746790` on `node+0x40`), then walks it |
| object list | slot `0x6c` `0x02747818` | the list of render objects |
| draw done and flip | slot `0xec` `0x020350c4` | `GX2DrawDone`, then the swap in `0x0274c8c4` |
| GPU timing | `0x0274c038` | four `GX2GPUTimeToCPUTime` reads: the title's own frame statistics |
| frame counter | `0x02760e58` | `display+0x78` advances; `display+0x80` takes `OSGetSystemTime` |
| wait | slot `0xe4` `0x0274c874` | the only pacing in the whole display path |

Two things follow, and they are what a second paint per tick rests on.

**The paint holds nothing that a second pass would consume.** The tree walk is `0x02746790`
to `0x02747c6c` to `0x02747bdc`, and `0x02747bdc` is this in full: draw the node through the
vtable at `node+0x2c` unless `node+0x44` bit 0 is set, then recurse the sibling chain at
`node+4` unless `node+0x44` bit 1 is set. It reads flags and pointers and writes nothing: no
cursor, no pop, nothing to rewind. The frame function around it is straight-line calls. So
painting the same tick's tree twice in one tick is not fighting a consumed stream; it is
calling the same function again with the same tree.

**The frame rate is one thing.** `0x0274c874` is
`do { GX2WaitForVsync(); GX2GetSwapStatus(&requested, &done, ..); } while (done < requested);`
and the flip is `GX2SwapScanBuffers()` in `0x0274c8c4`, taken when `display+0x28 == 2`. The
title calls `GX2SetSwapInterval(2)` once (ISSUE-003 in wiiuport), so a frame is two vblanks
and the display thread runs at 30 Hz. `0x0274c00c` is `do { vtable[0xcc](display); } while
(true)`, so the display thread paces itself and nothing in the frame function asks the logic
thread for anything. Presentation at 60 Hz is therefore this thread's swap interval and its
paint count. One caveat, because it is the one place a second paint could still stall: slot
`0xdc` also calls `0x02799c70`, `0x0272a8c4` and `0x0272ad80`, which are not read yet, and
any of them could be where the paint waits for the tick. A run answers that; the static
claim does not.

**Where the logic's rate comes from is not in these functions.** The logic frame is
`0x0203593c`, which reaches the tick `0x025f172c` and returns; the tick advances its own
counter at `0x1048d0a8` and compares it against a period at `0x1048d0ac`, and it contains no
wait and no loop either. The frame is reached through a 16-byte descriptor table at
`0x10005000` -- entry, `0x00140000`, stack -- which `0x02035b88` and `0x020355f8` start. So
whatever paces the logic thread is outside all three, and has not been read yet. It is a
question a run answers rather than the reverse: if the display paints twice a tick and the
logic rate stays 30 Hz, nothing was slaved to the flip; if it doubles, the gate belongs in
the logic path and its rate is the measurement that says so.

**The per-object draw, and therefore the place a blend belongs.** The tree walk reaches each
object's draw through the vtable at `node+0x2c`, slot `+0xc`. One class is confirmed: vtable
`0x10036300`, slot `+0xc` = `0x02160018`, which takes the node and a sub-pass index, and for
each of three sub-passes binds vertex, geometry and pixel uniform *blocks* and then calls
three more methods on the node through its own vtable `+0x2c`. What it holds is a per-object
draw record: the node keeps an array of them at `node+0xa4` with a count at `node+0xa0`, five
or six words each, and the record carries a display list at `+0`, an optional pointer at `+0xc`
to three int16 uniform-*block* indices (vertex, geometry, pixel) and an optional second
pointer at `+0x14`. The block's address and size are not in the record: they come from a
descriptor list at `param_2+0x14`, an array of `0x1c`-byte entries counted at `+0x4c`.

### The node, its records, and where the matrix actually is

Read further on 2026-09-26. The chain is the game's own all the way down, and the last link is
not what the section above guessed.

The node object is built by `FUN_0215d9d4`, which allocates 0x264c bytes and sets, in order:
its vtable at `+0xc` to `0x1001061c`; two sub-objects at `+0xa1c` and `+0xac4`, with vtables at
`+0xa28` (`0x1016ef84`) and `+0xad0` (`0x1016efb4`); a four-slot pool of 0x254-byte draw
records at `+0xa8`; and a 0x2f0-byte block at `+0xb38`.

Which class draws it, and through which slot, took a second read to get right. The tree walk's
leaf, `0x02747bdc`, calls slot `+0xc` of the vtable at `node+0x2c` when `node+0x44` bit 0 is
clear, and recurses into `node+4`'s list when bit 1 is clear. The class the tree actually holds
is the derived one at `0x10036300`, whose slot `+0xc` is `0x02160018`; the descriptor the
constructor installs, `0x1001061c`, has `0x02161028` in that slot, and `0x02161028` is a *reset* --
it clears two 0x4a8-byte records and re-stores the descriptor at `+0xc`. So `0x1001061c` is the
base class's descriptor and `0x10036300` is the class that draws, and they are not two names for
one slot. An earlier reading of this section had it the other way round.

`0x02160018` walks the node's own draw records: the array at `+0xa4` with a count at `+0xa0`,
five or six words each, and `param_2+0xc` selects which of three sub-passes is being drawn. A
record carries a display list at `+0`, an optional pointer at `+0xc`, a pointer at `+0x10` to
a small table of int16 uniform-block indices, and an optional pointer at `+0x14`.

**The two sub-objects are uniform-block binders, and that is the useful part.**
`0x1016ef84` slot `+0x2c` is `0x027ff88c` and `0x1016efb4` slot `+0x2c` is `0x027ff9c0`; the two
are the same function apart from which triple of indices they read -- `param_2+0x10+0x28`
against `+0x3c` -- and both do this and nothing else:

```
iVar2 = param_1 + 0x10 + *(int *)(param_1 + 0x4c) * 0x1c;   /* one past the last entry */
uVar4 = *(undefined4 *)(iVar2 + 0xc);                        /* the block's offset */
uVar6 = *(undefined4 *)(iVar2 + 4);                          /* the block's size   */
GX2SetPixelUniformBlock(iVar1, uVar4, uVar6);
GX2SetVertexUniformBlock(iVar5, uVar4, uVar6);
GX2SetGeometryUniformBlock(iVar2, uVar4, uVar6);
```

So the block's address and size are computed by the game's own code, per object, per pass, at
the moment it binds them -- from a descriptor list of 0x1c-byte entries counted at `+0x4c`.

**Which corrects the guess above.** The pose is *not* a field of the node. The matrix is inside
the uniform block's memory, and the node's draw only names the block. (The 0x2f0-byte block at
`+0xb38` is not it either: the constructor fills it with `0.0f` from `0x10145180` and `1.0f`
from `0x1014517c`, and those two ones sit at `+0x1c` and `+0x2c` into it, which is not a 3x4 laid
out any way -- an earlier reading of that as an identity matrix was wrong, and the constants
say so.)

What this changes for the blend: the hook that has the object's identity *and* the block's
address and size in hand at the same time is the binder, one function the game already calls
once per object per pass -- not the node draw, and certainly not the 110 call sites that bind
uniform blocks across the shader families. A stand-in for `0x027ff88c` would see, for every
object the title draws, which block it is about to bind and how big it is.

### The game keeps two of them, and says so in its own constructor

The sub-object that owns the descriptor list is built by `FUN_027fb40c`, and the two lines that
matter are these:

```
FUN_028effd0(param_1 + 0x10, 2, 0x1c, FUN_027beb5c);   /* two entries, 0x1c bytes each */
*(undefined4 *)(param_1 + 0x4c) = 1;                    /* and the count starts at one   */
```

**Two slots, and a count that starts at one.** The binder reads
`param_1 + 0x10 + *(int *)(param_1 + 0x4c) * 0x1c` -- entry *number count*, one past the last
one counted -- so the count is a cursor over a two-entry ring rather than a length, and the entry
being bound is the one at the cursor. That is the title's own double buffering of a per-object
uniform block, in the title's own code, and it is the same double buffering the host-side
mechanism had inferred statistically from block addresses recurring at one frame parity.

What is *not* yet read: whether the two slots are two frames or two passes. A text search for
the code that advances `+0x4c` returns 1797 functions, because `0x4c` is a common offset, so
that search cannot decide anything and the narrow route is the object's own method table. Read:
the vtable the sub-object's constructor installs at `+0xc` is `0x1016ef24`, and none of its
methods touches `+0x4c`. What they are is instructive -- `0x027fb528` and `0x027ff838` are its
reset and destructor, `0x027fb6a0` declares attribute layout, `0x027fb780` resets eight blocks
of attribute defaults, and `0x027fb880` fills three attribute streams from a source. Not one of
them writes a uniform block.

**So the block is written outside the object, before the object is drawn.** The list is prepared
per frame, and the object's own method is only handed the finished thing to bind. That has a
consequence for the blend, and it is the useful one: there are two distinct moments, not one.
The *values* exist at fill time, on the logic thread, before any draw; the *identity and the
address* are known at bind time, on the display thread, per object per pass. A blend therefore
has to capture at fill and write at bind -- or write at fill, using the other of the two slots.
Either way it is a pair of hooks in the game's own code and neither of them is the 110 call
sites.

Still open, and the next single read: who fills the entry at the cursor. Not one of the
candidates so far is it -- a search by offset cannot be, and the object is not where it is.

**The game names its own view uniforms.** Its rodata carries `cWorldViewMatrix[0]` at
`0x10163bb4` and `cWorldViewProjectionMatrix[0]` at `0x10163d00`, beside `uBlurOffset`,
`uOneMinusNearDivFar`, `cAngleScale`, `cColorScale`, `cInvTexSize`, `cFrameRCP1H` and
`cToyCam_Saturation1`, all referenced from one name-table function `0x02786520`. The matrix
this document's first section finds by watching which shaders share an orthonormal 3x4 and
how it moves is, in the title's own words, a uniform called `cWorldViewMatrix`.

### The display loop, byte for byte, and what a second paint costs

The display thread's whole entry point is eleven instructions, `0x0274c00c` to `0x0274c034`,
and `0x0274c038` -- the GPU-timing function -- begins immediately after, so there is no slack
past the last one. Read out of the title's own image:

| address | word | instruction |
|---|---|---|
| `0x0274c00c` | `7c0802a6` | `mfspr r0,LR` |
| `0x0274c010` | `9421fff0` | `stwu r1,-0x10(r1)` |
| `0x0274c014` | `93e1000c` | `stw r31,0xc(r1)` |
| `0x0274c018` | `7c7f1b78` | `or r31,r3,r3` |
| `0x0274c01c` | `819f0014` | `stw r0,0x14(r1)` |
| `0x0274c020` | `819f0024` | `lwz r12,0x24(r31)` -- loop: the vtable |
| `0x0274c024` | `800c00cc` | `lwz r0,0xcc(r12)` -- the frame |
| `0x0274c028` | `7c0903a6` | `mtspr CTR,r0` |
| `0x0274c02c` | `7fe3fb78` | `or r3,r31,r31` |
| `0x0274c030` | `4e800421` | `bctrl` |
| `0x0274c034` | `4bffffec` | `b 0x0274c020` |

Two consequences. The frame is reached through an **indirect** branch, so anything executable
can stand in for it without a branch's 32 MiB reach being a limit -- and the title keeps the
frame pointer in the vtable rather than in the loop, so a stand-in that re-reads
`lwz r0,0xcc(r12)` follows whichever display class the title actually installed. There are two
such classes: the vtable at `0x10004e88` (slot `0xdc` is `0x02034ffc`, slot `0xec` is
`0x020350c4`) and a second at `0x10145000` (same slots `0xc4`/`0xcc`, but `0xdc` is
`0x0274c7e4` and `0xec` is `0x0274c8c4`).

And the swap interval is not a constant: the one call, `0x0274bafc` to the `gx2` import
`0x028fad2c`, passes `display+0x50` -- `lwz r3,0x50(r26)` at `0x0274baf8` -- and that is the
same field `0x0274c874` tests to decide whether to wait for the flip at all. So the field
both sets the interval and enables the wait, and the title sets it to 2.

**A stand-in for the frame, in eleven words, all of them the title's own.** Writing this into
executable guest memory and pointing the vtable's slot `0xcc` at it makes the display thread
paint each tick's tree twice and present both, with the frame still read from the title's
vtable at run time:

```
819f0024  lwz  r12,0x24(r31)      819f0024  lwz  r12,0x24(r31)
800c00cc  lwz  r0,0xcc(r12)       800c00cc  lwz  r0,0xcc(r12)
7c0903a6  mtctr r0                7c0903a6  mtctr r0
7fe3fb78  or   r3,r31,r31         7fe3fb78  or   r3,r31,r31
4e800421  bctr                    4e800421  bctr
                                  4e800020  blr        <- from 0x025f0950
```

Every word is lifted verbatim from the addresses above, so nothing here is hand-assembled and
nothing rests on a displacement field worked out by hand. `r31` is already the display
(0x0274c018) and is callee-saved across the frame, so the first paint is handed the same
argument the original call was. 44 bytes.

Two things about where it returns, both measured rather than read. It cannot return with
`blr`, because the game's `bctrl` is the only thing that set the link register and a stand-in
that also calls the title's own `GX2SetSwapInterval` overwrites it -- the `blr` then lands
inside the stand-in and repaints for ever. And it must return to the loop at `0x0274c020`, not
to the thread's entry at `0x0274c00c`: the entry is a prologue that opens a fresh stack frame
and takes the display pointer from `r3`, so returning there re-frames the stack once per paint
and loses the display. A stand-in that returned to the entry ran seven seconds and then faulted
at `0x0274c020` with `r31` zero -- `lwz r12,0x24(r31)` on no display -- which the emulator's
crash dump reported as the active instruction and the register, and nothing in the stand-in's
own source did.

**What this does not yet establish.** Whether the second paint draws the same image is a
question about the game's own state, and the loop above is where the risk is: the frame
function ends with `if (display+0x74 & 1) display+0x74 ^= 2` and skips the flip when both bit 0
and bit 1 of that field are set, so painting twice per tick may leave every second paint
without a flip. That field's value in the steady state is not read yet, and neither is
`display+0x28`. Both are readable at run time from the display pointer, which a probe on
`0x0274c264` already receives in `r3` on every paint.

## Limits of what has been measured

**The camera finding rests on four consecutive frames** captured at frame 300 of an
unattended boot — one scene, one viewpoint, no input driven. It is enough to identify
the transform, because 71 shaders sharing one orthonormal matrix is not a coincidence
that four frames could manufacture. It is **not** enough to claim the same offsets hold
elsewhere: the offset differs per shader already, so later shader families will use
others. Anything built on this must find the camera by its properties at runtime, not by
a table of offsets recorded here.

**No frame has been captured with input driven**, so the camera has only been seen
moving on its own. Whether player-driven motion differs in kind is untested.

**The call-shape inventory above came from a separate run** of about two minutes that
reached only the title's early stages, so it is not complete for the whole game: shader
families used later will add slots. Any policy built from that table must fail loudly on
an unknown slot rather than assume the list is exhaustive.

**Which renderer served either run is not established.** An earlier note here claimed the
software rasteriser; that was never measured and the one probe since points the other
way, so nothing in this document should be read as depending on it.

### What the first measured run of the mod said

Measured 2026-09-26 on the real title, headless and offscreen on the RX 6700 XT, from a
save that reaches Outset Island, with the runtime's own caller census on `fapGm_Execute`
(`0x025d42ec`) so the logic's rate is counted at the function that runs the tick rather
than at a frame counter the flip also moves. One window, six seconds, 180 of each:

| | paints | logic ticks |
|---|---|---|
| the title as shipped | 180 in 6.0 s = **30.00/s** | 180 in 6.0 s = **30.00/s** |

So the two rates are equal before anything is changed, which is the denominator every later
number is read against: the display thread paints once per tick and the logic ticks once per
paint.

The display object's own fields, read through the probe that sees it in `r3` on every paint:
`display+0x28` phase 2, `display+0x50` interval 2, `display+0x74` flags **0**, `display+0x78`
0. The flags matter: the frame function ends with `if (display+0x74 & 1) display+0x74 ^= 2`
and skips the flip when both bits are set, so painting twice a tick was expected to leave every
second paint without a flip. With bit 0 clear the toggle is never taken, so that risk is not
real for this title -- read, not assumed. `+0x78` did not advance over the window, so whatever
counts frames there is not the counter this mod reports its own rate from.

The stand-in's block comes from the loader's trampoline area, at `0x00e05850` when it is
reserved at link time and `0x00e07068` when it is reserved later, which is inside the
recompiler's executable area (`PPC_REC_CODE_AREA_END` is `0x10000000`) and is the same arena the
caller-census probe stubs live in.

Being inside that area turned out not to be sufficient, and the way it was not sufficient is
worth more than the number. A stand-in whose body is the display loop's own five instructions,
reached through the display vtable exactly as the title reaches its own draw, froze the whole
emulated system for precisely as long as it was installed: no paints, no logic ticks, nothing
logged, and 30 a second the moment it was taken out again. The same block, the same words, the
same single word of vtable rewritten, reached by a plain branch instead of through the count
register, runs the title at 30.00 paints and 30.00 logic ticks a second with the stand-in in
place. `mtctr`/`bctr` against `b` is the whole difference, and it is the recompiler's jump
table: a direct branch translates at the address it lands on, an indirect one looks its target
up there, and a block allocated out of the trampoline arena had never been registered. The
runtime registers it now.

For the title this changes nothing about what may be patched -- a slot of a vtable the display
already calls, with the frame re-read from the title's own vtable on every pass -- and it is
worth stating that the constraint it does impose is the emulator's, not the game's.
