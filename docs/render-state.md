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
