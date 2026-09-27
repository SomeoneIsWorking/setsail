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

The vtable the sub-object's constructor installs at `+0xc` is `0x1016ef24`, and none
of its methods touches `+0x4c`. What they are is instructive -- `0x027fb528` and
`0x027ff838` are its reset and destructor, `0x027fb6a0` declares attribute layout,
`0x027fb780` resets eight blocks of attribute defaults, and `0x027fb880` fills three
attribute streams from a source. Not one of them writes a uniform block.

**So the block is written outside the object, before the object is drawn.** The list
is prepared per frame, and the object's own method is only handed the finished thing
to bind. That has a consequence for the blend, and it is the useful one: there are
two distinct moments, not one. The *values* exist at fill time, on the logic thread,
before any draw; the *identity and the address* are known at bind time, on the
display thread, per object per pass. A blend therefore has to capture at fill and
write at bind -- or write at fill, using the other of the two slots. Either way it is
a pair of hooks in the game's own code and neither of them is the 110 call sites.

What is *not* established by reading the code: whether the two slots are two frames
or two passes. A text search for the code that advances `+0x4c` returns 1797
functions, because `0x4c` is a common offset, so that search cannot decide anything.
Narrowed to the module that builds the list -- `0x027f0000`-`0x02810000`, which holds
the constructor, both binders and the entry initialiser -- it returns **thirteen**
functions that store to `+0x4c`, and *none of them turns the cursor*: two set it to
one, two set it to zero, one copies it from `+0x48`, and the rest store through a
different base register, which makes them a different class's field that happens to
sit at 0x4c. The one that copies from `+0x48` is `FUN_027fb678`, and it is not this
list: it computes `countLeadingZeros` and walks a linked list at `+0x54`, which is a
tree node, not a descriptor ring.

So the code does not say, and the honest position is that the answer is a
measurement: the census now reads **both** slots on every binding and counts how
often the cursor moved between consecutive bindings of the same object, against the
number of bindings that could have been a switch at all.

**Measured, and it is two frames.** Over 3,025,779 bindings across 583 objects in
one driven run, the cursor read entry 0 on 1,514,669 of them and entry 1 on
1,511,110 -- an even split, which is what a two-slot ring looks like -- and it
moved on **898,547 of 3,023,213 repeat bindings, 0.297 per bind**. Both slots in
equal measure rules out a cursor that never turns. A third of a switch per binding
is what per-*frame* turning looks like: an object drawn in three passes inside one
frame produces two consecutive bindings with no move and one across the frame
boundary that does, and 1/(3-1) is 0.5, 1/(2-1) is 1.0, and the observed 0.297 sits
where two or three passes per object per frame puts it. A cursor that flipped per
*bind* would have switched on every repeat binding, near 1.0.

So the two slots are two frames, and the consequence is the one a blend needs:
**when tick N binds, the other slot still holds tick N-1's values.** Both ticks'
poses are in memory at the moment the draw happens, so an in-between frame is a
lerp of two reads of the title's own state, and nothing has to be recorded and
replayed. That is the question this document said had to be measured rather than
assumed, and it is now measured, with the denominators above.

**Still open, and the next single read: who fills the entry at the cursor.** Not one of
the candidates so far is it -- a search by offset cannot be, and the object is not
where it is.

**The entry's word at `+0x04`, and the pose, are both now read, and they were read by
following the binder rather than by guessing.** The word at `+0x04` read `0x3e634300`
on a real binding and was called a pointer rather than a length, which was right and
left it unexplained. It is the *block's own address*: the two slots of every object
measured are exactly `0x100` apart, five objects in a row, and the word at `+0x0c`
that the binder passes to `GX2Set*UniformBlock` is `0x40` for every one of them -- a
constant, so an offset within the block and not a size. So a uniform block is 256
bytes, its address is in the descriptor, and the two the ring turns between are 256
bytes apart in the title's own heap.

A first attempt resolved that address the other way, by trying each word of the
entry, adding the entry's own offset and keeping the first that read. It found an
address, and it found the *object* -- whose vtable and heap pointers read perfectly
well, `0x140` before where the block is. "An address that reads" is worth nothing,
and the report now carries offsets and says they are offsets.

**The pose is at `+0xc4` of that block: twelve floats, and they are a rigid transform — but
only at the moment they were dumped, and this section's claim is withdrawn as a statement about
the block when the binder names it.** Measured on the real title, with a probe on the binder
reading the block it is about to hand the GPU, on the display thread inside the title's own
draw: over **236,694 bindings, no rigid transform at `+0xc4` in any of them**, and **233
whole-block scans of four blocks, every 4-aligned offset, none anywhere in any of them.** The
block is 256 bytes and its ring's two slots are `0x100` apart, and at the moment it is bound it
holds no transform at any offset.

The twelve floats below are real. What is wrong is the moment: they were dumped while the title
was **held at a frame's end**, which is after the draw, and the blend runs at the bind, which is
before it. So this is a dump of a block at a moment when the block had been filled, and not a
statement about what is in it when the binder names it. **Withdrawn:** that `+0xc4` holds the
pose as a fact about the bound block, and with it the idea that the binder is where a blend
reads the pose from. The fill site is.

**And the fill site is not the binder's siblings.** The binder is a method on a sub-object — the
object it is handed *is* the sub-object, and the descriptor's entries are at `object + 0x10` —
and the method table is **in the image**:

```
0x1016ef90  0x027ff96c   84 addresses
0x1016ef98  0x027fba24  112 addresses
0x1016efa0  0x027fba94   56 addresses
0x1016efa8  0x027fbacc  140 addresses
0x1016efb0  0x027ff88c  224 addresses   the binder
0x1016efb8  end of the table
```

Five methods, eight bytes an entry, and the binder is the only one of the five that walks the
descriptor — four have no line mentioning the cursor at `+0x4c` or the `0x1c` entry stride, and
the binder's has exactly one, `param_1 + 0x10 + *(int *)(param_1 + 0x4c) * 0x1c`. So whatever
fills the block is not on this object, and the ring's two entries exist so the GPU is not
reading a block that is being written rather than to carry the previous tick — which is the same
finding as the other slot reading zero at the pose's offsets, from a different direction.

This also corrects an earlier note here, that the sub-object's methods "are dispatched through a
vtable that has no references to follow". There are no references because the table is reached
through a pointer the sub-object carries; the pointers are in the image, and the one naming the
binder is at `0x1016efb0`. Following the call graph was never the way in.

**Why the block held no transform: it is 64 bytes.** The binder's second argument is the
descriptor entry's word at `+0x0c`, and it reads `0x40` for every object measured — but `0x40`
is the block's **size**, not an offset inside a 256-byte block. In the emulator's own
`GX2SetVertexUniformBlock` the three arguments are `(index, size, address)` taken from
`hCPU->gpr[3..5]`, which settles it. A 64-byte block cannot hold twelve floats, so the 233 scans
were reading a window around a block that was never going to contain one, and the two findings
agree.

**And the node's own draw says where the pose really is.** `vtable 0x10036300` slot `+0xc` is
`FUN_02160018` — 1,536 addresses — and it is the node's draw:

```
uVar1  = *(uint *)(param_2 + 0xc);                             /* which draw record */
puVar7 = *(undefined4 **)(param_1 + 0xa4);                     /* the node's record array */
if (uVar1 < *(uint *)(param_1 + 0xa0)) puVar7 = puVar7 + uVar1 * 5;   /* 5-word stride */
puVar7 = (undefined4 *)*puVar7;                                /* the record */
GX2CallDisplayList(*(undefined4 *)(pbVar5 + 4));               /* the draw is a display list */
iVar8 = *(int *)(*(int *)(param_2 + 0x14) + 4);                /* the sub-object */
iVar8 = iVar8 + 0x10 + *(int *)(iVar8 + 0x4c) * 0x1c;         /* the binder's own arithmetic */
```

So the chain in the objective's framing is real and has addresses: **node → `+0xa4` → a
5-word-strided record array → the record → a pointer whose shorts at `+0xc` and `+0xe` are a
range of uniform block indices.** Two shorts two bytes apart is a range, which is the "uniform
block index" — and the block it indexes is addressed through GX2's own uniform block table, not
through the sub-object's descriptor.

Note also that the node's draw computes the sub-object's descriptor entry **itself**, with the
binder's exact arithmetic, in the same function. The binder and the draw are two readers of one
descriptor; following the call graph from either would have found the other, and the earlier note
here that the sub-object's methods have no references to follow is why it was not followed.

**So the pose is in the block the record's index range names, and the emulator already holds
it.** `LatteFrameHooks::UniformAssembly` records per draw the assembled uniform `data` and
`sizeInBytes`, the guest `blockAddresses` the draw sourced as `(bufferId, physicalAddress)`
pairs, and on the `DisplayList` it belongs to **whose draw it is**. The pose is therefore inside
the bytes the game itself assembled for a *named node's draw*: its offset within them is found
once, by the rigid-transform test over a bounded set of draws, and is then a constant. And
whether tick N-1's values are present when tick N paints is answered by the frame recording the
emulator already keeps.

**This document's earlier reading is corrected by it.** The claim that "a blend cannot read N-1
out of the ring" was true of the ring and irrelevant: the ring's 64-byte blocks are not where the
pose is, so the ring was never the place N-1 would have come from.

**And it is not in the assembled uniform buffers either — so it is a node field.** The emulator
hands over every uniform buffer the game assembles for a draw, with the guest blocks it sourced
and the display list it belongs to. Every 4-aligned offset of every one of them was tested for a
rigid 3x4, with the counts kept:

```
window 0:  614,690 assemblies,  2 candidate offsets,  0 believed at 20%,  best offset null
           371,528 of them had no block sources at all
window 1:  756,350 assemblies,  2 candidate offsets,  0 believed at 20%,  best offset null
           456,968 of them had no block sources at all
```

No offset cleared the bar, and the two candidates are coincidences a colour triple or three
equal rows would produce. Three fifths of the draws source no uniform blocks at all.

That agrees with the 64-byte finding and explains it. **The title positions geometry on the CPU
each frame** — the shipped mechanism's own evidence in this project says so, and says why it had
to keep vertex bytes and blend them — so the pose is in the vertex data, not in a uniform, and
the transform that puts it there is the node's own, applied before the display list is built.

**So the chain in the objectives' framing is right read literally — "which *node field* holds the
pose" — and this document went looking in uniform blocks** because the binder names one and
because the block census was the instrument to hand. Two measurements in a row now say the
block is the wrong place. The next read is the same shape test applied to guest memory: at the
node's own draw, `FUN_02160018` with the node in `r3`, scan the node for a rigid 3x4 at every
4-aligned offset, with the same counted bar. Lerping *that* field and letting the game's own
draw run is what regenerates the skinning, the attributes and the display list at the lerped
pose — with no host-side vertex work at all, which is why `VertexBlend` guessing which vertex
buffers belonged to one object is a consequence of not knowing this and not a preference.
The original dump:
Dumped from the title while it ran, one slot against the other, 256 bytes each:

```
   (   0.638175,    0.010258,   -0.769823 )
   (   0.586924,    0.640629,    0.495090 )   translation (22547.72, -8514.89, -6188.70)
   (   0.498250,   -0.767782,    0.402813 )
```

Row lengths `1.000000 1.000000 1.000000`, and the three row dot products
`0.000000 0.000000 0.000000`. Unit length and mutually perpendicular to six decimal
places is what makes it a transform rather than three rows of numbers that happen to
be near unit length, and the translation sits beside it in the same 12 words. The
fourth float of each group of four is zero, so it is a 3x4 and not a 4x4 with a
row dropped.

**And the other slot at those same offsets is zero.** Not a previous pose: nothing.
Which is the finding that matters, and it cuts against the paragraph above. The
cursor turns -- 0.297 switches a binding, measured -- but a slot the title has not
written reads as zeros, so *the cursor turning is not the same thing as the previous
tick's values being in memory*. Counting non-zero words settles it: across four
objects the two slots read 19 and 52 non-zero words of 64, the same for every
object.

So the two readings are different findings and the earlier one was the wrong one. The
ring turns; what the two slots hold at the moment of a bind is one transform and one
unwritten block.

**Withdrawing a claim made in the course of finding this.** A first reading of the
same dumps said the pose was "unchanged while the camera turned" and called that
evidence it was not a per-tick pose. **The camera did not turn.** The turn went in as
`POST /input?rightx=0.5&reads=60` and the title's own `cWorldViewMatrix[0]` at
`0x10163bb4` read the same 16 floats before and after -- 0 of 16 changed. The pose
not moving across a camera turn that did not happen says nothing at all, and the
inference drawn from it is withdrawn. It was caught by checking the input against
the title's own view matrix rather than against a count, which is the only reason
it was caught at all; the measurement is now written to refuse to report a pose
result when the view matrix has not moved.

What *is* measured about the pose over time: with the title still, 0 of 16 blocks
changed over 1.2 seconds. That is the expected result for a pose the title writes
only when something moves, and it is equally the result for a pose nobody writes,
so it does not distinguish them. Whether the pose at `+0xc4` is per-tick is **not
established**, and the read that would settle it is the same one: a camera turn
verified against `cWorldViewMatrix[0]`, then the pose read before and after. Turning
the camera through the control channel at all is the step in front of that, and it
is not yet done.

**The game names its own view uniforms — and the addresses this document gave for them
are the names, not the variables.** Its rodata carries `cWorldViewMatrix[0]` at
`0x10163bb4` and `cWorldViewProjectionMatrix[0]` at `0x10163d00`, beside `uBlurOffset`,
`uOneMinusNearDivFar`, `cAngleScale`, `cColorScale`, `cInvTexSize`, `cFrameRCP1H` and
`cToyCam_Saturation1`, all referenced from one name-table function `0x02786520`. The matrix
this document's first section finds by watching which shaders share an orthonormal 3x4 and
how it moves is, in the title's own words, a uniform called `cWorldViewMatrix`.

**What those two addresses are, measured.** Dumped from the running title and read
as text:

```
0x10163bb4: "cWorldViewMatrix[0] uBlurOffset uOneMinusNearDivFar "
0x10163d00: "cWorldViewProjectionMatrix[0] cViewLightDir cDepth[0] cCol..."
```

**They are the uniform names, in the rodata name table -- not the variables.** A name
in a table is where the shader compiler put the string, and nothing ever writes it.
So they are a uniform-name list, which is worth having on its own: it says the
matrix is a uniform and what the title calls it. It is not where the value lives,
and any tool that reads one of these addresses reads the name. The earlier claim in
this document, and in the objectives this work answers, that these are the addresses
of the view matrices is withdrawn.

This also explains a measurement that was taken to mean something and did not: the
pose at `+0xc4` was reported as "unchanged when the camera turned", with the camera
turn verified against `cWorldViewMatrix[0]` reading the same 16 floats before and
after. That comparison was a string compared with itself, so it was always going to
agree; the check looked like a control and was not one. **The view matrix's address
is not known**, and finding it is the read in front of every pose measurement.

**The chain from the name to the value's address, read out of the code.**

`0x02786520` is the registration pass, and it fills in nothing: 5,372
instructions, 955 calls to 16 distinct functions, and 559 of its 561 stores are
stack spills. What it does is bind a name to a *slot*. The most-called callee,
`FUN_027bb0ec` at 252 calls, is the whole of that:

```
puVar2 = *(undefined4 **)(param_1 + 0x2c);   /* a table of pointers */
if (param_2 < *(uint *)(param_1 + 0x28)) { puVar2 = puVar2 + param_2 * 4; }
*puVar2 = *param_3;                          /* the address, stored at a slot index */
```

and then the same store repeated across a table of `0x84`-byte records, from
`*(param_1 + 0x7c)`, bounded by the count at `*(iVar1 + 0xc)`. So a uniform is bound
to a **slot index in a per-shader table of pointers, and the pointer is the address
its value lives at**. A second shape exists -- `FUN_0278b9cc` allocates an 8-byte
cell on demand and stores a value and a vtable pointer in it -- so some uniforms are
bound to freshly allocated cells rather than to a table slot.

**So the view matrix's address is a pointer the pass is *handed*, and the pass has
exactly one caller: `FUN_027b59f4`, 360 addresses, called once.** That caller stores
no address of its own, so the addresses come from its own base or its own
parameters. That is the next read and it is bounded: one function.

The chain so far, with every address it came from:

| what | where | what it says |
|---|---|---|
| the name | `0x10163bb4` | the string `cWorldViewMatrix[0]`, in the rodata name table |
| the pass that registers it | `0x02786520` | 955 calls, 16 callees, 559 of 561 stores are spills |
| how a name is bound | `0x027bb0ec` | a pointer stored at a slot index in a per-shader table |
| where the address comes from | `0x027b59f4` | the pass's only caller, and it stores no address itself |

The view matrix's address is therefore not a constant anywhere in the title: it is
passed in, once, by one 360-address function. That is a better shape than a fixed
address would have been -- a value the title hands to every shader is a value the
blend can be handed too -- and it is why the pose at `+0xc4` and the camera's place
are not obviously the same thing.

**The rest of that chain, read from the running product rather than the file.** The three
globals the call chain names are zero in the static image -- the loader fills them -- so the
last link can only be read live, and it was:

```
value at 0x101f8c14          0x21f0a0d8
word at 0x21f0a0e8 (= that + 0x10)   0x21f0a15c     the address the registration pass is handed
```

64 words at `0x21f0a15c`, of which **7 point into MEM1** (`0x101459e0`, `0x10163630`,
`0x10145c00`, `0x10145c30`, `0x1015e618`, `0x10143aa4`, `0x10163618`), beside `0x00800000`,
`0x00000038`, `0x00001d30`, `0x00000058`, `0x00000020`, the fragment `arc\0` and the tag
`0x5874556d`. The word at index 7 is the table's own address, so this is a structure of
pointers to structures rather than a flat list of uniform addresses.

**A caution, stated because the numbers invite the wrong reading.** `0x10163618` and
`0x10163630` sit in the same rodata region as the uniform *names* at `0x10163bb4`, and the
words beside them are a fragment of a filename and a four-character tag. So this structure
reads more like a graphics or asset context than like a table of uniform value addresses, and
the chain's `DAT_101f8c14` may be a display context the registration pass is handed rather
than the uniform table itself. **The view matrix's address is still not known.** What is
established is the mechanism -- a uniform is bound to a slot index in a per-shader table of
pointers, and the pointer is handed in by one 360-address function -- and that the addresses
exist only in a running product, not in the file.

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

The stand-in that works is therefore the one that does *not* re-read the frame: it branches
straight at the frame the vtable slot held when it was installed, and the install check refuses
by name over a slot that does not hold this title's frame. The cost is exact and worth stating
-- a title that swapped that slot at runtime would keep painting the frame that was verified --
and the benefit is the whole mechanism, since the re-reading form does not run at all.

Two paints in one iteration, though, is a different matter: calling the frame twice with `bl` took
the emulator down with signal 11 at a host address on the first frame, because the frame returns
through `blr` and the payload's own call had put the link register inside the stand-in's memory.
A return into the loader's trampoline arena does not work here, which is the same class of failure
as the indirect call and points at the same thing: register-indirect branches whose target is that
arena.

So the working form does everything on the way out. It asks the title's own
`GX2SetSwapInterval(1)` -- the call at `0x0274bafc` made with one instead of what `display+0x50`
held -- puts the link register back where the loop's own `bctrl` at `0x0274c030` left it, and
reaches the frame with a plain branch so the frame's return goes to `0x0274c034`, the loop's own
branch back to its top.

**Which makes the rate the interval's doing, not the second paint's.** The frame waits for its
flip and the flip is what paces the loop, so one vblank a flip is what doubles the picture. The
second paint is still wanted -- it is what will carry the blend -- but it cannot be a second call
inside one iteration, and where it has to come from instead is the next thing to work out: an
iteration that paints the blend and an iteration that paints the tick's own frame, chosen by a
counter, each still leaving by a branch into the title's own code.

For the title none of this changes what may be patched: a slot of the vtable the display already
calls, and the frame function it already points at. The constraint the indirect call and the return
both impose is the emulator's, not the game's.


## Where the pose is not, and what the scan had to be corrected for first

The objective asks for a **node field**. Three places have now been read and three came back
empty, each with its denominators: 233 whole-block scans of the binder's 64-byte block across
every 4-aligned offset, 756,350 assembled uniform buffers, and 8 distinct nodes at 4 samples of
647 words each. The title positions geometry on the CPU each frame, which is why the shipped
mechanism had to keep vertex bytes and blend them rather than blend a transform -- so the
transform is one an object carries, and it has to be read.

**The node's own draw cannot be probed where the vtable points.** The vtable at `0x10036300`
slot `+0xc` holds `0x02160180`, 0x168 bytes *into* `FUN_02160018`, and that address's first
instruction is a conditional branch (`0x41820010`) -- a probe resumes at "the instruction after
the entry", so a taken branch there would make the stub re-run the code the branch was there to
skip, and the emulator refuses such a site outright. The function's own entry is safe
(`stwu r1,-0x148(r1)`, `0x9421FEB8`) and the node is in `r3` there, and a second table in the
image at `0x10010648` dispatches through it -- **and it takes zero calls.** The title dispatches
the draw only through the vtable's target, so the entry is not the path.

**Which leaves the draw's own route to its sub-object**: the draw calls its sub-object at
`node + 0xa1c`, and the binder probe on that sub-object is already installed and already firing
137,489 times a run, so the node and the sub-object are both one fixed arithmetic away from a
binding the title makes hundreds of thousands of times.

**What is there is static.** With one sample per object per frame -- four samples, a frame
apart -- every rigid transform in both places is `0 moved, delta 0`: node 320, 1340 and 2360,
and sub-object 792, each in 5 or 6 of 8 objects. Bind poses, rest poses, basis tables: the same
shape at the same offset in most objects, and the same value for ever. Not a pose.

So the remaining question is one a rigid test cannot ask: is the node's own transform **absent**,
or **present and carrying scale**? If present, the parent chain is only needed to compose with
it; if absent, the transform a renderer multiplies -- the world matrix, the node's place in the
graph multiplied with its parents' -- is on the parent and nowhere else. A second class counts
any non-singular 3x3 for exactly this, with a floor of 1e-6 on the determinant so a plane of
near-zero numbers does not read as a matrix.

### Four things the instrument got wrong before it got anything right

The scan produced a **positive** answer twice, and both were the instrument rather than the
title. They are recorded because each would have been a committed wrong turn.

1. **"Moved" was a bitwise test, not a motion test.** The report said `moved 18` beside `biggest
   delta 0.000000`: values differing in the last mantissa bit, printed as zero. Three node
   offsets and one sub-object offset were "held by 6 of 8 objects" on that basis. The bar is
   now a change over 1e-3 between two draws a frame apart, and an offset is named only if it
   both crosses the cross-object count *and* has been seen to move.
2. **The two windows overlapped.** `kSubObjectOffset` is 2588 bytes and the scan window was
   4096, so a node's window reached into its own sub-object and the sub-object's `+80` was
   reported in the node's table at `+2668` -- one measurement counted twice, which is the exact
   thing the two tables exist to prevent. The node's window now ends where the sub-object
   begins.
3. **The samples were per binding, not per frame.** An object is bound several times per frame,
   so all four of its samples could land inside one frame, where no pose has moved. The report
   gave `0 moved, 18 still, delta 0` -- identical to a genuinely static field, and with no way
   to say which it was looking at. The schedule is now one sample per object per frame, read
   from the title's own paint counter, and the report says which schedule ran.
4. **The scale was subtracted twice.** Row length is stored as a deviation from 1 and the report
   took one off it again, so a scale of 2.5 came out as 0.5.

And one constant, which is the rule this project already had: the image's word at the draw's
entry is `0x9421FEB8`, a value derived from the signed decimal the disassembler prints came out
as `0x9422FEB8`, and the refusal -- `entryHeldOther` -- read exactly like a real finding about
the game. Every payload word is lifted from the image, never derived, because a derived one is a
word nobody checked.


## The pose is not held anywhere as a transform, and that redirects the blend

The objective asks for "which node field holds the pose". It was looked for in four places,
with a working identity and a sample schedule that puts every comparison a frame apart, and it
is not in any of them.

| place | samples | what is there |
|---|---|---|
| the node's own leading 2588 bytes | 8 objects x 4 frames | transforms, all static |
| the sub-object's 4096 bytes at `node + 0xa1c` | 8 objects x 4 frames | transforms, all static |
| the binder's 64-byte uniform block | 233 whole-block scans | nothing |
| 809,682 assembled uniform buffers | 75,703 repeat comparisons per offset | nothing rigid in 20% of them, and nothing that moves |

**The identity was the thing that made the last row mean anything.** The fork's own header
called `blockSources` "the engine's own storage for the object, and the only identity a
recorded draw carries", and measured it matched **one** identity across the 438,872 assemblies
that had sources -- the uniform block is re-uploaded at a new guest address each frame, so the
address set is nearly unique per draw. That gave the movement test 63 comparisons to work with.
Using the node, which the binder already publishes and the GX2 hook cannot see, gives 75,703.
Same bars, same run: a thousandfold more comparison, and the answer does not change.

**So the title keeps no pose at draw time.** The only values that move are at row scales of 4
to 81, which are projection constants and coordinates rather than transforms. This is
consistent with how the game works and with why the mechanism being retired existed: the title
positions geometry **on the CPU each frame** and hands GX2 a display list of
already-transformed vertices, so the pose has already been consumed into vertex bytes by the
time anything could read a field. `VertexBlend` existed to paper over exactly that.

That makes the blend's landing place the **vertex stream at the game's own draw**, not a field
to lerp, and the fork already has both halves of it: the uniform assembly's data is writable at
the last point before the buffer is uploaded, and the draw observer hands over vertex
replacements at the draw. Identity is the node -- the objective's own answer, and now the one
the code actually has.

Recorded here because it is a change of mechanism rather than a smaller version of the same one,
and because the question the objective phrases has a definite answer: the pose is not held
anywhere as a transform.


## Where the position attribute is, measured from the title's own tables

Because the pose is consumed into vertex bytes, the blend writes vertex bytes, so the one thing
that had to be *known* is which attribute carries the position. It is measured rather than read
out of a GX2 header, by how often each `(semantic, format, size, buffer, offset)` signature
recurs across the title's own objects:

    502,922 guest draws, 916,081 attributes read, 7 objects tracked (386,949 refused),
    0 draws with no attributes, 1,994 with no node published, 0 naming a buffer the draw lacks

    position: semantic 0, format 0x00000030, 12 bytes, buffer 0, offset 0, per instance 0
      in 7 of 7 objects and 71,165 draws

The near-misses are in the report and they matter. A *second* twelve-byte format-`0x30`
attribute sits at offset 16, in 4 of 7 objects and 39,689 draws -- it clears the bar of 4 on its
own. It is not named because the one at offset 0 is in 7 of 7, and a reader can see both. A
report that filtered the runner-up out would have shown one line and called it a finding.

What the format byte *is*, is not guessed: `0x30` is what the title pairs with a twelve-byte
three-component position in 7 objects and 71,165 draws, and `0x1e` with the eight-byte ones.
What `0x30` is called in Latte's enumeration is a lookup, and the report carries the byte in hex
and in decimal so a reader need not take this one's word for it.

The sampling limit is stated rather than buried: seven objects of the first eight the binder
published, 386,949 refused, and those seven may be seven instances of one kind of thing. "7 of
7" and "7 of the first 7" are not the same statement, and only one of them is what the number
says.


## The position is per vertex layout, and the layout is in the key

The two-tick falsifier said 2 of 8 nodes blendable and 5 identical, and the split was by
**stride**: the 5 identical nodes were at stride 32 and compared cleanly -- 585, 975, 1235, 845
and 4 vertices, zero differing bytes, every magnitude believable -- while the 2 were at strides
of 20 and 64, with 18 and 60 components out of range.

The cause was in the census's own comparison key, and it is worth stating because it is the
kind of thing that reads as working. `Signature` recorded a stride and the key **ignored** it, so
a stride-32 draw and a stride-20 draw whose attribute fields agreed folded into one signature and
the majority counted both. That is how a single global position came to be reported. The
attribute the census named sits at offset 0 *of its own layout*, and a title packs positions
differently per vertex layout -- so one global offset is one layout's answer, and reading the
others with it produces floats of 10^38.

The stride is in the key now, the position is asked per layout with its own denominator, and the
report lists **every layout** -- because the number of layouts is exactly what the one global
answer was hiding.

A separate correction to the same theme: the falsifier was sampling the *first* draw of each
node each frame, and a node's first draw is a single-vertex placeholder (36 bytes at a stride of
32). Six of eight objects therefore compared a placeholder against a mesh and reported a "shape
change" that never happened. Samples are matched by the draw's own shape now, and a node that
really does change mesh between ticks reports "nothing paired" with the shapes it did sample,
rather than a verdict about a comparison that never took place.

And a number that looked like evidence: the run reported component deltas of 1.06e+38 and called
them movement. A position does not move by 10^38 between frames, so there is now a stated
ceiling, the unreadable components are counted, and a believable movement is separable from
unreadable bytes -- 40 differing bytes with a largest component delta of **0.488** is a
half-unit of travel, and it is now reported as such beside the 18 components that were not
readable.


## The falsifier's answer, spread across the run

Sampling the *first* eight objects gave "6 of 8 identical" -- which for a wind game's opening
frame is plausibly a sea, a sky and a particle system, and is a statement about those eight
rather than about the title. The sample is strided now: an object is tracked only when it is the
first of its own 4096th arrival, so the eight tracked spread across the whole run, at frames
109, 132, 159, 180, 204, 225, 253 and 293.

**The answer changes with the sample.** 500,896 draws seen, 8 tracked, 47 refused by the set
bound:

    3 blendable, 1 identical, 1 valueUnchanged, 3 with nothing paired

    1166878616: blendable,       4 vertices, stride 20, 38 differing bytes, delta 0.106766738
    1216241436: blendable,       4 vertices, stride 20, 42 differing bytes, delta 209089
    1160909272: blendable,       4 vertices, stride 20, 40 differing bytes, delta 883540
    1046048488: valueUnchanged, 10 vertices, stride 152, 80 differing bytes, delta 9.1e-07
    1160952552: identical,       3 vertices, stride 32, 0 differing bytes, delta 0

**A largest component delta of 0.107 is a tenth of a unit of travel, which is what a position
does.** So there is something real, and a sea and a sky not moving is why the first sample found
none of it.

**The layouts account for every unreadable magnitude, and show where the census is still wrong:**

    stride 20: 7 objects, semantic 0, 12 bytes, offset  0
    stride 28: 1 object,  no position named
    stride 32: 7 objects, semantic 0, 12 bytes, offset  0
    stride 48: 3 objects, semantic 0, 12 bytes, offset 16
    stride 64: 7 objects, semantic 0, 12 bytes, offset 16

The position is at offset 0 in two layouts and offset 16 in two others, so the single global
offset the census named first was right for half the title and nonsense for the rest.

And the stride-20 layout is the one still unsolved: four vertices at a 20-byte stride with a
12-byte position at offset 0 leaves 8 bytes of something else in the stride, and those are read
as floats. But a *believable* 0.107 on the same twelve bytes is impossible if all three
components were wrong -- so those twelve bytes are partly position and partly not, and a bar over
how many objects agree on a signature is not enough to tell that. The next bar is a magnitude
condition rather than a count.


## Withdrawn: the believable 0.107 was the census reading a non-position

An earlier entry in this file reported a largest component delta of **0.106766738** on the
stride-20 layout and called it a tenth of a unit of travel, "which is what a position does", and
said there was something real. **That was wrong.** Those twelve bytes at offset 0 are not a
position -- one component in them reads as 3e+38, which is what the out-of-range count had been
saying all along. A delta of 0.107 beside a delta of 1e+38 in the same twelve bytes was never a
position.

With the census refusing any position whose components have ever read as something a position is
not, the layouts are:

    stride 20: 7 objects, positionKnown=false
    stride 28: 1 object,  positionKnown=false      (one object cannot clear a cross-object bar)
    stride 32: 7 objects, semantic 1,  12 bytes, offset 12
    stride 48: 3 objects, semantic 14, 16 bytes, offset 0
    stride 64: 7 objects, positionKnown=false
    stride 80: 2 objects, positionKnown=false
    stride 96: 5 objects, semantic 4,  12 bytes, offset 48

**Seven layouts, the position at a different offset in each.** The stride-32 answer moved from
`semantic 0, offset 0` to `semantic 1, offset 12`, and stride 64 names nothing at all -- so the
census was giving a position for two of the four layouts it claimed one for, and only a count of
agreement had let that through.

The falsifier on the corrected positions: 488,712 draws seen, 403,774 with no position named, 4
nodes tracked, **0 blendable** against 3 identical. The refusals rose from 188,522 to 403,774
because most draws are now correctly refused -- their layout has no position this census will
name. **The vertex-stream blend has no ingredient on these objects, and the one time it appeared
to have one, the census was reading bytes that are not positions.**

Four of the seven layouts are *unresolved*, which is the honest word: the magnitude bar refuses
them rather than naming a position and reading rubbish. A layout the census has not solved is a
different thing from a layout with no position, and the report says which.


## Every layout is refused, and that is the answer

With the denormal floor's non-zero clause in place -- a vertex at the origin is a position, a
1.7e-38 denormal is not -- the census refuses **all eight** of the title's vertex layouts, and
the histogram says why with a number: at the stride-32 offset 0, in 7 objects and 15,976 draws,
**136,381 components implausible**, against a 1% bar. 479,158 draws seen and 479,158 with no
position named.

So the position attribute cannot be identified in any layout by the title's own attribute table.
Not "the position does not move" and not "the blend is hard": at every candidate offset roughly
one vertex in ten reads as something that is not a position.

The falsifier, with no position to read, has nothing to compare -- 0 of everything, 0 nodes
tracked. That is not a negative result, it is the absence of a measurement, and it is reported as
such.

**Where the objective's own terms stand.** Measured on the real title, with every instrument
corrected against its own false positives:

1. ~~**No node field holds the pose.**~~ **Withdrawn** -- see "The descriptor record holds no
   block address" below. The node's leading 2,588 bytes and the sub-object's 4,096 at
   `node + 0xa1c` were read with a working identity and frame-apart samples, and everything in
   them is static, so *those* two scans stand. The binder's 64-byte block and the 838,155
   assembled uniform buffers do not: both read the object's own structure rather than a uniform
   block, and "every transform in every one is static" was a true statement about something else.
   The question is open again.
2. **The title consumes the pose into vertex bytes**, which is why: it positions geometry on the
   CPU each frame and hands GX2 a display list of already-transformed vertices. That is also why
   the mechanism being retired needed `VertexBlend`.
3. **The position attribute cannot be found by the title's own attribute tables**, in any of
   eight layouts, because the candidate offsets are not positions for a substantial minority of
   vertices.

**The remaining route is the one the objective names and the attribute table does not carry: the
vertex shader's own input declaration.** The draw gives the fetch shader's attribute table, whose
`semanticId` is an index whose *meaning* lives in the shader's input declaration -- and that
declaration is in the guest's shader memory, not in the draw. Guessing that `semantic 0` means
position is precisely the assumption every measurement in this log exists to refuse, so it has not
been made.

## The descriptor record holds no block address, and the 64-byte "block" was the record itself

The binder at `0x027ff88c` / `0x027ff9c0` was decompiled to find the block's address. It reads:

```c
uVar6 = *(uint32 *)(iVar2 + 4);      /* third argument  */
uVar4 = *(uint32 *)(iVar2 + 0xc);   /* second argument */
GX2SetVertexUniformBlock(iVar5, uVar4, uVar6);
```

and on the host side `external/cemu/src/Cafe/OS/libs/gx2/GX2_shader_legacy.cpp` writes one of
those two into the uniform block register as `memory_virtualToPhysical(...)`, **with nothing added
to it**. So the record's two words are the address and the size and **there is no base to find** --
an earlier measurement that histogrammed `address - offset` over 180,707 bindings was computing
the difference of a size and an address, and is deleted.

**The records, quoted raw** (four of them, from the report's `sampleRecords`):

```
object 0x3e595304: [0x3e5953d0, 0x3e595400, 0x3e595400, 0x40, 0x40, 0x03010000, 0x10163e00]
object 0x3e597adc: [0x3e5957c0, 0x3e5957e0, 0x3e5957e0, 0x40, 0x40, 0x03010000, 0x10163e00]
object 0x3e5976e0: [0x3e5972c0, 0x3e5974e0, 0x3e5974e0, 0x40, 0x40, 0x03010000, 0x10163e00]
object 0x3e5972e4: [0x3e5972c0, 0x3e5974e0, 0x3e5974e0, 0x40, 0x40, 0x03010000, 0x10163e00]
```

Read against `object + 0x10`, which is where `readEntry` starts:

- Words 0, 1, 2 are **pointers into the object's own structure** -- `object + 0xcc`, `object +
  0xec`, `object + 0xec`. That is why five of the seven words "read as guest memory": they point
  into the object's own mapped neighbourhood. They were never block addresses.
- Words 3 and 4 are **both `0x40`**. The binder hands `GX2Set*UniformBlock` the pair
  `(0x40, 0x40)`, so the register holds `0x40` where the binder wrote. **There is no block address
  in this record.**
- Word 6 is `0x10163e00`, 0x24c past `cWorldViewMatrix[0]` at `0x10163bb4` -- the record points
  into the title's global data, not at a uniform block.

**Which voids the "233 whole-block scans agreed" evidence, and says exactly why.** The 64-byte
block was `entry[1]` used as an address, and `entry[1]` is `object + 0xfc`. So all 233 scans read
**the object's own descriptor neighbourhood**, 0xfc bytes into the object, and agreed because they
were 233 readings of one piece of static structure. The same goes for the 838,155 "assembled
uniform buffers": those addresses come from `blockSources`, which reads word 0 of the bank the
draw's *shader* names, while the guest writes each bank by the index it passes to
`GX2Set*UniformBlock`. Two different numbers, so the value read is whatever last wrote that
register slot -- 1,555 distinct values over 382,575 sourced addresses.

So **"every transform in every one is static" is withdrawn.** It was a true statement about the
title's own object structures and about a register file, and it was read as a statement about the
uniform blocks. Neither scan read a uniform block.

**Measured over 142,682 exact per-object pairs, no word of the record matches any address the
draw sourced** -- the best word hit 3 times, a share of 2.1e-05 against a 50% bar. That is the
negative result, and it is now negative for a known reason rather than for a suspected one.

**Condition 2's second question: answered yes.** The ring is fed the title's own two record words
-- the address and the size the binder passes to `GX2Set*UniformBlock` -- and over 178,021
bindings it finds **8 objects naming 16 distinct block addresses**, one transition per object, which
is double buffering measured. The ring never compares across an address change, so each of its
**16 of 16** "still present" verdicts is between two bindings of the same object at the same
address, at least two ticks apart: the previous use of that address is still there when the next
tick binds.

**The scan against the real address is negative too.** `ObjectPoseHistory` now gets the same
address the ring re-reads; it used to get the record's *size* word, `0x40`, as though it were an
address, so every reading was 64 bytes of one location. Read where the binder says the block is:
**236,161 observations, 0 whose block looked like a pose, 0 unreadable, and 233 whole-block scans
with 0 offset hits.** A real negative, and it retires the third place to look -- consistent with
the other two, because the title positions geometry on the CPU and hands GX2 vertex bytes, so
there is no transform left in a uniform block.

**The ring's verdict is 15 to 16 of 16 across runs**, not 16 of 16: one run of identical code
reported one comparison overwritten, so the bytes do change sometimes and the comparison is not
trivially always-equal.

**And this is not the block the withdrawn scan read.** Those 233 scans read `object + 0xFC` --
the record's own word 1 used as an address -- while these addresses sit far from their objects
(leading offset 0xA7C44, 16 distinct offsets over 8 objects). So "every transform is static" was
never a statement about these 64 bytes, and the pose scan has to be redone against this address.

**What this reopens.** The objective's first question -- which node field holds the pose -- was
answered "none" partly on the strength of those two scans. That answer does not stand, and the
o start again from a real uniform block. The pool is real, and the title names its block by a
register index.

**The size word tells the guest's writes from register leftovers.** Word 1 of a uniform block
register is `size - 1` as the guest wrote it, and a size the guest chose is a small constant that
register state does not invent -- so it can say a slot the title filled from one it did not, where
word 0 alone cannot, since the guest indexes these registers by the index it passes to
`GX2Set*UniformBlock` and the shader names them by its own group. The fork now hands both words
over (`LatteFrameHooks::UniformAssembly::blockSizes`). With the record's own size word as the
filter and nothing guessed:

```
expected size 64 bytes, 3,990,665 size words read, 1,000,430 slots holding size-1
  0x4581c200: 17,806   0x4581c300: 17,045   0x45436700: 14,939
  0x45436300: 10,930   0x45978b00: 10,496   0x3e634300:  4,145
```

**0x100-strided** -- `0x4581c200` to `0x4581c300` is 0x100, `0x45436300` to `0x45436700` is 0x400
-- which is a pool of 64-byte blocks, and `0x3e634300` is in it. That is the value an earlier
comment in wiiuport's log dismissed as "a pointer, not a length". It was a block address; what it
was not was reachable by the route being tried at the time.

**The join is the index, and it is in the binder's own `r4`.** The decompilation puts the block
index outside the record: `*(short *)(iVar3 + 0xc)` with
`iVar3 = *(int *)(param_2 + 0x10) + 0x28`, and `param_2` is `r4` at the probe. So the title names
its block by a *register index*, read from a structure the census does not yet read, and the
block's bytes are in the slot that index addresses. r3 gives the object, r4 gives the indices, and
`contextRegister[mmSQ_VTX_UNIFORM_BLOCK_START + index * 7]` word 0 gives the address. No base, no
offset, and nothing matched host-side.

## The vtable slot the stand-in overwrites is the one the payload reads

Building the objective's own eleven words and running them on the real title: **no fault, and no
paint** -- 1,854 paints at 68.0s and 1,854 at 97.1s, the gate reading 1,854 calls at the probe and
nothing in it, and the capture refused with no image reaching its slot in 25 seconds.

The reason is in the payload's second word, and it is not a missing register:

```
0x10004e88 + 0xcc = 0x10004f54
```

`0x10004e88` is the vtable the mod reports from the running display, and `0x10004f54` is the slot
the objective names as the one to rewrite with the stand-in's address. So `lwz r12, 0xcc(r0)` --
with `r0` holding the vtable, the convention the objective's own `0xcc` displacement implies -- reads
**the stand-in's own address**, `mtspr CTR` takes it, and `bctrl` calls the stand-in again.

**Condition 1 asks for two things that are the same word**: reach the frame by rewriting vtable slot
`0xcc`, and re-read the frame from the title's own vtable. A stand-in that reaches the frame through
that slot calls itself. The signature is distinct from the literal-`bl` family, which faults on a
guest load at address `0x198`: a self-call that never reaches the frame leaves the paint count
exactly where it was, which is what the run shows.

**It is resolvable from inside the mechanism, and the resolution is one value.** The mod reads the
vtable out of the running display on every arming, reads slot `0xcc` to learn what the title was
going to call, and checks the frame's entry word against the image before installing anything -- so
it knows `0x0274c264` as the slot's *original* contents. That value, not the rewritten one, is what a
payload reaching the frame through the vtable needs.

The first word has a second problem: `lwzu r3, 0x24(r30)` presumes `r30` holds the display, and the
update form leaves `r30` advanced by `0x24`, so the second group reads `display + 0x48` rather than
where the first read.

## The double-paint fault is not in the title's own code

Two independent runs of the two-paint stand-in under gdb, each with the capture workload the fault
needs, both faulting the same way. The backtrace is the **interpreter**, not recompiled code:

```
#0  ppcMem_readDataU32 (address=1763)                    at PPCInterpreterImpl.cpp:72
#1  PPCInterpreter_LWZ (Opcode=2147682018 = 0x800306e2)  at PPCInterpreterLoadStore.hpp:285
#2  PPCInterpreterSlim_executeInstruction                at PPCInterpreterImpl.cpp:1257
#3  coreinit::__OSFiberThreadEntry                       at coreinit_Thread.cpp:1365
```

The handler computes `(rA ? gpr[rA] : 0) + imm`, so with `imm = 0x6e2` and `rA = 0` the guest read
guest address `0x6e2` and `r0` was zero. The other run's opcode was `0x800006e2` -- the same
displacement off `r0`, a different destination register.

**And that instruction is not in the title's RPX.** Over the analyzed program:

```
scanned 9,432,460 executable bytes in 17 blocks
  control 0x7c0802a6 (the display frame's first word, mfspr r0): 23,265 matches
  sought  0x800006e2 (lwz r0,0x6e2(r0)):                         0 matches
```

The control being found 23,265 times is what makes the zero a result rather than a broken search.
**So the faulting code is in coreinit, rpl or another of the title's RPX files, and not in
`cking.elf`.** The question is therefore no longer what state the display object leaves behind; it is
which library function runs on the second pass with `r0 = 0`. Nothing establishes that the display
frame is not re-entrant -- that was inferred from where the fault surfaced, and the surface is the
emulator's fallback interpreter.

## The frame's own first words, and an offset that was wrong

Read out of the listing's own bytes rather than from notes:

```
0x0274c264  0x7c0802a6  mfspr  r0                <- SPR 8, the link register, into r0
0x0274c268  0x9421ffe8  stwu   r1,-0x18(r1)
0x0274c26c  0x93c10010  stw    r30,0x10(r1)
0x0274c270  0x93e10014  stw    r31,0x14(r1)
0x0274c274  0x9001001c  stw    r0,0x1c(r1)
0x0274c278  0x7c7e1b78  or     r30,r3,r3           <- the display pointer
0x0274c27c  0x4bffedd9  bl     0x0274b054
0x0274c280  0x807e0018  lwz    r3,0x18(r30)        <- the first sub-object
```

The listing this project has been quoting started at `0x0274c278`, so it **omitted the whole
five-word prologue** and showed the `lwz` at an address two words later than the image's. Two
consequences:

- **The first sub-object is at `display+0x18`, not `display+0x24`.** Every claim that the frame's
  call targets come from `*(display+0x24)` is wrong by an offset, and the display probe that reads
  them through `+0x24` has been reading a field the frame does not read.
- **The frame's first instruction clobbers `r0`** with the link register. A stand-in that expects `r0`
  to survive a call into the frame is expecting a register the callee's first instruction overwrites.

## The gdb numbers for the fault do not survive a second run, and the image does not contain the
## shape the fault was reported with

Two runs of identical code reported the faulting effective address as 1762 and then 1763, the opcode as
`0x800006e2` and then `0x800306e2`, and the guest program counter as three different values. One
fixed instruction cannot be all of those, so the `0x6e2` displacement and the `r0 = 0` are read off a
backtrace frame that had already been unwound. **Both are withdrawn.**

Checked against the image instead, where nothing depends on gdb:

```
scanned 29,408 functions, matching on the full instruction text
  0x6e2(r0):  0 instructions in 0 functions
  0x6e2(  :   2 instructions in 2 functions   -- lbz r0,0x6e2(r31) at 0x021c54e0
                                                -- lbz r12,0x6e2(r3) at 0x021c5cb8
  control, 0x3c(:  3,047 instructions in 1,608 functions
```

**The title's code contains exactly two loads at displacement `0x6e2`, both `lbz`, neither off `r0`.**
So the fault is not this title's draw path. The fault arrives through `PPCInterpreterSlim_executeInstruction`
-- the recompiler's *fallback* -- which means **the second pass is running where the recompiler
declined**, and that is a fact about the patch rather than about the title.

## The running guest's memory is not shown to be the disc image's

With the debugger's guest-memory read repaired, it read guest memory for the first time. The
addressing is right -- `memory_base` came back `0x7ffed4000000` and every read is that base plus the
guest address -- and the words found are **not** the words the image has at those addresses:

```
the frame, guest 0x0274c264:     0x1c966b4a 0xe8ff2194 0x1000c193 0x1400e193 ...
the vtable slot, guest 0x01004f4c: 0x00000000 0x00000000 0x00000000 0x00000000
the stand-in block, guest 0x00e05898: 0x01006038 0x9154af49 0xc5699449 ...
```

The vtable slot reads as zeros where the mod says it wrote the stand-in's address, and the stand-in's
block reads as words that are not the payload. Three explanations fit and one measurement would
choose between them, so none is claimed: the code and data are **encrypted on disc and decrypted into
place**; or the frame is in a **different module** than the one analysed and `0x0274xxxx` is not its
load address at run time; or the mod reports host-side addresses where the guest wants guest ones.

**Until that is settled, no disassembly-derived claim about the running title is established** --
including the `display+0x18` correction, which is a correction to the analysed listing. This is the
first prerequisite for the paint path, and it is now the project's open question.

## The guest is the disc image: the debugger was reading it backwards

The section above said the running guest's memory did not match the disc image's, and listed that as
the project's open question. **Both halves of that are withdrawn. The image is the guest, and the
debugger was reversing every word it printed.**

The product's own accessor settles it, and it is a read that refuses by reason rather than one that
returns whatever the host had there -- `GET /memory` goes through the fork's
`GuestCallProbes::GuestBytes`, which returns null unless every byte of the range is mapped guest
memory:

```
  the display frame, guest 0x0274c264, as the product reads it
    4a6b961c 9421ffe8 93c10010 93e10014 9001001c 7c7e1b78 4bffedd9 807e0018
  the display frame, guest 0x0274c264, as gdb's x/8wx read it
    1c966b4a e8ff2194 1000c193 1400e193 1c000190 781b7e7c d9edff4b 18007e80
  every one of the eight byte-reversed: True
```

Eight words, eight reversals, one of them the frame's own `or r3,r30,r3` -- no coincidence produces
that. **gdb reverses every word it prints for big-endian guest memory**, so every guest word read
through it in this project was byte-swapped.

**The one word that genuinely differs is the paint mod's own probe, and it is a branch because that is
what a probe is.** `GuestCallProbes::Install` writes a relative branch over the probe's entry and
keeps the image's word inside its stub, and the arena shows that stub's own layout: `040004e4` (the
HLE `bl`), `7c0802a6` (the displaced `mfspr r0`), `3d80027f 618cf890` (the resume address),
`7d8903a6` (`mtctr r12`).

**The vtable slot, read by the product, agrees with the objective's arithmetic:**

```
  guest 0x10004f4c:  0274c00c 00000000 0274c264 00000000 0274c67c 00000000
                     vtable+0xc4  vtable+0xcc = the frame   vtable+0xd4
```

`0x10004e88 + 0xcc = 0x10004f54` holds `0x0274c264`. The mod refuses to install unless that slot holds
the display frame, so **the mod working is itself the evidence that the guest is the image** -- the
check that had looked like a contradiction was the check that proves it.

## The frame's display fields, measured rather than quoted from its prologue

The frame's first eight words were read directly and showed its first load at `display+0x18`, which
briefly looked like a correction to the `*(display+0x24)` the call targets come from. It is not.
All 85 instructions of the frame, with `r30` holding the display from its sixth word to its exit:

```
  READ off r30:    +0x18 once (0x0274c280), +0x24 five times (0x0274c288),
                   +0x28 (0x0274c35c), +0x4c twice, +0x74 twice (0x0274c2c4)
  WRITTEN via r30: +0x28, +0x74 (0x0274c38c), +0x78, +0x7c, +0x80, +0x84
  loads off r10/r11/r12: +0xd4, +0xdc, +0x6c, +0xec, +0xe4 -- the five call targets
```

`+0x18` is read once into `r3` early; `+0x24` is read five times, and every one of the five call
targets is loaded through a register the `+0x24` chain supplies. **The paint mod's offsets are
confirmed against the image**: its call-target base of `display+0x24` and its five offsets
`{0x6c, 0xd4, 0xdc, 0xec, 0xe4}` are exactly the frame's own access pattern. The objective's two
named fields are confirmed too -- `+0x74` read twice and written once at `0x0274c38c`, which is the
documented `stw r0,0x74(r30)`, and `+0x28` read once and written once.

## The faulting instruction, decoded with the byte order right

With the reversal undone, the opcode the interpreter was executing is `0xe2060380`, which is
`lwarx r16,r6,r0` -- a load-and-reserve, the shape a lock takes and not the shape a display path
takes:

```
scanned 9,432,460 executable bytes in 17 blocks
  control 0x7c7e1b78 (the frame's own sixth word): 4,893 matches
  sought  0xe2060380:                                    0 matches
```

**So the faulting instruction is not in this title's own RPX** -- and unlike the earlier version of
that claim, this one survives the byte-order fix. What is consistent across every run of the fault:
the program counter is in the loader's arena at `0x00e000xxx` and the link register is inside the
stand-in's block. The second paint enters the arena and leaves it executing something outside the
title's code, and the arena is where the mod's stand-in and its probes live.

## The objective's payload hands the display frame the wrong pointer

The frame takes the display and dereferences `+0x24` itself -- measured from all 85 of its
instructions, not quoted from a prologue:

```
0x0274c278  or    r30,r3,r3        the display pointer, from r3
0x0274c280  lwz   r3,0x18(r30)     the display's +0x18
0x0274c288  lwz   r10,0x24(r30)    the call-target base, read five times in the function
0x0274c28c  lwz   r12,0xd4(r10)    a call target, off that sub-object
```

The payload's first word does that dereference in the caller -- `lwzu r3,0x24(r30)`, then
`or r31,r3,r3`, then `bctrl` -- so `bctrl` calls the frame with `r3` = the **sub-object**, not the
display. The frame's `or r30,r3,r3` then makes `r30` the sub-object, and every field it reads is the
sub-object's. **`+0x24` is read five times and each read feeds a `bctrl` target**, so the wrong level
of indirection does not merely read the wrong fields: it dispatches through targets read out of
whatever the sub-object points at.

The `lwzu` form compounds it -- the update leaves `r30` advanced by `0x24`, so the payload's two groups
are two passes over two different addresses, not two over the same tree.

**So the payload has two independent defects, neither of them a missing register:** word 1
pre-dereferences the call-target base for a frame that wants the display, and word 2 reads the slot the
mod has just rewritten, so `mtspr CTR` takes the stand-in's own address. A payload with eleven words has
one call target and one call site; this one has two of each and they disagree. Both were predicted by
the mechanism's own measurements before the payload was run, and the run agrees -- no paint, no fault.

## The loader arena's base is the HLE registry, not code

`MEMORY_CODE_TRAMPOLINE_AREA_ADDR` is `0x00E00000` with a 2 MiB size -- the area
`RPLLoader_AllocateTrampolineCodeSpace` hands out from, and the area the recompiler is registered for
wholesale at init because the loader does put real code in it. Its first `0x38` bytes, read as bytes:

```
0x00e00000  04 00 01 96  04 00 02 78  04 00 02 8d  04 00 02 91   HLE calls, one per entry
0x00e00030  04 00 02 c2  04 00 02 ff  4e 80 00 20                then `bctr`
0x00e00038  6e 6e 5f 61 63 74 2e 46 69 6e 61 6c ...              nna_act.Finalize__Q32_2nn3actFv
0x00e00060  00 00 00 00 ...                                       zeros
```

`0x0400xxxx` is cemu's HLE call encoding -- `1u << 26 | hleIndex`, the same shape a probe's dispatch
stub uses -- so the arena's base is the **HLE function registry's code, then its symbol names, then
zero padding**. The mod's stand-in is at `0x00e05898`, about 22 KiB past that, and a probe stub sits
at `0x00e058b4`.

The double-paint fault's program counter is in that range on every run (`0x00e0006a8`, `0x00e000768`,
`0x00e000e28` across three), so **a branch into the arena lands in the registry table or the zeros
after it and executes data as code.** That accounts for the whole signature with no appeal to the
display's state -- and it makes the display object being cleared a consequence of the frame never
having been entered rather than a cause. Which branch goes there is still unknown; the candidates are
the stand-in's control flow after the frame returns, or one of the frame's five `bctrl`s, whose targets
come from `display+0x24` and are measured identical across paints.

## The paint payloads were branching into a zero-filled hole, and the fault has moved three times

Read live at the fault, in one pass from one register so that nothing had to be paired up afterwards:

```
program counter  0x0e001128
link register    0x00e058a0        the stand-in's own block (0x00e05898) plus 8
the opcode in ESI 0x800006e2       rA = 0, displacement 0x6e2
the effective address, in RCX: 0x000006e2
r0 = 0x00e05898   r11 = r12 = 0x10004e88   r31 = 0x43e08af8
```

**The link register is the stand-in's own, and its only branch before the frame is the swap-interval
call -- and that address is not code in this title's image:**

```
0x028fad2c  0x00000000   add r0,r0,r0
0x028fad30  0x00000000   add r0,r0,r0
0x028fad34  0x00000000   add r0,r0,r0
0x028fad38  0x00000000   add r0,r0,r0
```

Ghidra holds a function symbol at `0x028fad2c` and no instruction at all, which is a zero-filled hole
rather than a body it failed to disassemble. A `bl` into it runs four no-ops and then whatever follows
at `0x028fad3c` -- which is how a guest that was painting twice ended up executing host pointer bytes
in the loader's arena: `0x0e001128` read little-endian is the host pointer `0x7ffee2e2060080`.

**Fixed by deletion.** Nothing branches there any more; the interval is set by writing the display's
own `+0x50` field, which is the shape that measures 59.99 and 60.12 paints a second and survives. The
call was redundant before it was fatal. This project is what the title's image says on the subject, and
it says the address is a hole.

**The fault persists and its signature changed**, which is the evidence that the hole was a contributor
and not the whole cause. Before: a segfault inside the *interpreter's* guest load, program counter in
the arena. After:

```
rip  0x7ffe79a19f30   movbe 0x48(%r13,%rax,1),%ecx   with r13 = memory_base, rax = 0
OSSched[core=1]  via recompiled  guest pc=0x00e05884  lr=0x0274c280
  r0..r7 = 00e058a0 0e275a38 10008000 00000000 0e275a24 0e275a28 0e275a30 44213980
```

**The guest is inside a probe's dispatch stub.** The program counter is in the arena twenty bytes below
the stand-in's own block, and the arena is where the probe stubs live -- one was read at `0x00e058b4`
holding the HLE `bl`, the displaced word and the resume. The link register is `0x0274c280`, **the
display frame's own seventh word**, so the frame ran, it called a probe, and the guest is in that
probe's stub.

**So the fault has moved three times and each move narrowed it**: from the title's draw path, to the
loader arena, to a probe's dispatch stub. None of the three is the title's paint path, and the last is
not the paint mod's payload either -- it is the probe machinery installed on the frame. Nothing about
this title's own drawing is established to be at fault, and nothing about the pose or the uniform-block
ring is blocked by it.

## The paint probe sat on a word that reads the link register, and the frame returns through it

Read at the fault, with the guest's program counter and link register taken from the CPU state through
the register the recompiler reserves for it:

```
OSSched[core=1]  via recompiled  guest pc=0x00e0586c  lr=0x0274c280
  r0..r7 = 00e05888 0e275a38 10008000 00000000 0e275a24 0e275a28 0e275a30 44213980
```

**The display frame's first word is `mfspr r0, LR`, and the frame returns through what that instruction
produced:**

```
0x0274c264  0x7c0802a6  mfspr  r0, LR       SPR field 8, destination r0
0x0274c274  0x9001001c  stw    r0,0x1c(r1)  <- the link register, into the frame's own stack slot
0x0274c278  0x7c7e1b78  or     r30,r3,r3
0x0274c27c  0x4bffedd9  bl     0x0274b054
```

A guest probe's stub begins with an **HLE call** and runs the displaced instruction second, and a call
sets the link register. So probing the frame's first word made the frame save the stub's return address
instead of its caller's, and **return into the loader's arena** -- which is what the register pair at
the fault shows.

**Fixed in the mechanism, because the mechanism is what was wrong**: a probe now refuses an entry whose
displaced instruction reads `LR`, decoded from the opcode and the SPR field rather than matched on two
full encodings. The paint mod's probe moved to the frame's **sixth** word, `or r30,r3,r3`, which reads
no special register -- and `r3` is still the display pointer there, because the frame has not touched it
and its own first act is to copy it into `r30`. So the probe still receives the display in `r3`, which
is what the objective asks of it.

**And the fault persists, so this was necessary and not sufficient.** With the fix in, the register that
was wrong is right: `lr = 0x0274c280` is the frame's own seventh word, which is where a frame that
returned from its sixth word belongs. The guest still reaches the arena -- `pc = 0x00e0586c`, still in
recompiled code. The probe's `LR` was a real defect and is fixed; something else sends the guest into
the arena after the frame has returned.

**What this says about the title: nothing new is at fault in it.** Every location this fault has been
traced to -- the title's draw path, the loader arena's data, a probe's stub, a zero-filled hole the
payload called -- is code this project wrote, and the last two are now fixed. The remaining cause is in
what the stand-in does after the frame returns, and the title's own drawing has not been implicated at
any point.

## The fault is deterministic, and the title's frame returns correctly

With this project's two defects fixed -- the payload branch into a zero-filled hole, and the probe on
the frame's first word -- two independent runs report the fault's guest state **byte for byte
identically**:

```
OSSched[core=1]  via recompiled  guest pc=0x00e0586c  lr=0x0274c280  r1=0x0e275a38
  r0..r7 = 00e05888 0e275a38 10008000 00000000 0e275a24 0e275a28 0e275a30 44213980
```

**The display frame returned correctly.** `lr` is its own seventh word, which is where a frame that
returned from its sixth word belongs. **The guest is then at `0x00e0586c`, 300 bytes *below* the
stand-in's own block**, and the register file is not the guest's: `r1` is `0x0e275a38`, which is not a
guest address at all (MEM1 ends at `0x017fffff`, the loader arena at `0x00ffffff`); `r4`, `r5` and `r6`
are four words at four-byte spacing, the shape of a structure; and `r3`, which the frame's first act
copies into `r30` and which the probe reports as the display, is **zero**.

A register file holding equally spaced words and a stack pointer that is not a guest address is what
**executing data** looks like from the inside.

**The recompiler is registered for the whole of it.** The loader's trampoline area is registered with
the recompiler wholesale at startup, because the loader does put real code there -- which is correct as
far as it goes. But the area's base is the HLE function registry's dispatch stubs, then its symbol
names, then zero padding, and elsewhere in it the host's own bookkeeping. **None of that is guest
code, and a branch into it is translated as instructions.** That is why the fault's address has been the
same every run: the target is a fixed piece of the registry and the guest's path to it is
deterministic.

**So the remaining cause is not in the title.** A branch out of the frame's return path lands in the
loader's data, and nothing in the frame or the display object is at fault -- the frame returned
correctly, and the display's own fields were measured identical across paints. The discriminator for
the last step is already in hand: the second paint as a **tail branch** survives and the second paint
as a **call** faults, so the whole of what is left is what happens *after* the frame returns.

## The frame writes one word above its own allocation

Measured from the frame's own words, and worth stating before anything stands in for it twice:

```
0x0274c268  stwu  r1,-0x18(r1)     the frame is [old-0x18, old)
0x0274c26c  stw   r30,0x10(r1)     -> old-0x08   inside
0x0274c270  stw   r31,0x14(r1)     -> old-0x04   inside
0x0274c274  stw   r0,0x1c(r1)      -> old+0x04   FOUR BYTES ABOVE ITS OWN ALLOCATION
```

The frame stores a word into **its caller's frame** every time it is entered -- with a stand-in as the
caller, four bytes above the display thread's own stack pointer. It is the same address on the first
paint and the second, so on its own it is not what makes a second call differ, but it does mean a
stand-in in this title's return path is standing in a frame it is silently writing to.

## The tail-branch shape faults too, and the block the report names does not hold the payload

**The discriminator the port's notes offered is withdrawn.** `TailTwiceAtSixty` had been measured as
"painting nothing" back when it shared the paint payload's `bl` at `0x028fad2c` with the two-paint call
shape -- so that measurement was of a payload calling into a zero-filled hole and says nothing about the
shape. Re-run with the hole call gone:

```
  at rest:      installed False (twiceAtSixty), probe installed, block 0x00e05880, 1554 paints, interval 2
  armed mode 8: installed True  (tailTwiceAtSixty), probe installed, block 0x00e05880, 1555 paints, interval 1
  next read:    connection refused
```

The interval field reads **1**, so the field write that replaced the hole call works and the arming
succeeds. **Both two-paint shapes fault**, whether the second paint is a call or a tail branch, so "what
happens after the frame returns" does not separate them and the tail branch is not a workaround.

**And the block the report names does not hold the payload.** Read as bytes at the fault, with a
two-paint mode armed and the report naming the block:

```
0x00e05880  c1 a6 00 48  89 df e8 15  7e 14 00 e9  78 f7 ff ff
0x00e05890  48 8d 35 37  c1 a6 00 48  89 df e8 01  7e 14 00 e9
0x00e058a0  64 f7 ff ff  48 8d 35 0d  c1 a6 00 48  89 df e8 ed
```

That is not the payload. The payload for that shape is three words of branches, and every one has `0x48`
or `0x4b` in its top byte. What is there is a pattern repeating every `0x14` bytes whose words decode as
ordinary non-branching instructions -- `0xc1a60048` is `lfs f13,0(r0,r12)`, `0x89dfe815` is `lbzu` --
**so the address the paint mod reports as its own block holds, at the moment of the fault, a repeating
pattern rather than the branches it wrote there.**

Two readings fit and one measurement separates them, so neither is claimed: the block address moved
between the arming that was recorded and the fault, or something overwrote the payload after it was
written. The address is reported as `0x00e05898` in some runs and `0x00e05880` in others, and the
fault's program counter sits consistently *just below* the block in both armings.

This is the next thing to settle, and it is smaller than what came before: whether the words the mod
wrote are still at the address it wrote them to when the guest runs. The product's own `/memory` accessor
answers it.

## The payload is written correctly, and the block does not move

Read beside the arming, in the same pass, with a control read of the same block taken first:

```
  the block, before arming   guest 0x00e05880
    00000000 00000000 00000000 00000000 00000000 00000000 00000000 497cea54 00000000 ...

  armed paint mode 8
  the block, immediately after arming   guest 0x00e05880
    499469e5 499469e0 49946798 00000000 00000000 00000000 00000000 497cea54 00000000 ...
```

**The block did not move, and the three words written into it are exactly the payload:**

```
0x00e05880  0x499469e5  bl 0x0274c264   the display frame, called    <- paint 0
0x00e05884  0x499469e0  b  0x0274c264   the display frame, tailed   <- paint 1
0x00e05888  0x49946798  b  0x0274c020   the display thread's loop top
```

**So "the payload was not written there" and "something overwrote it" are both withdrawn.** The pattern
that appeared in an earlier dump is not what the block holds when the payload is written; that dump was
taken at the fault, well after the arming the harness recorded, and it is not reproducible by a read
taken beside the arming.

**And the port's probe was the source of the false lead.** It counted words whose top byte was `0x48` or
`0x4b` and reported "0 of 12 branches" for a block holding three. The absolute and link bits live in
bits 25 and 0, *inside* the top byte, so `bl` with `AA=0` is `0x49xxxxxx`. The primary opcode is bits
31-26 and is the same for `bc`, `b` and `bcl`; the probe now uses that, decodes each branch's target, and
carries a self-check against the words a payload is known to hold so a run that reports "no branches" on
a block full of them says its counts are meaningless rather than becoming a finding about the block.

What is left is not about where the payload is or what is in it: **the guest reaches an address just
below this block, with the payload correct above it.**
