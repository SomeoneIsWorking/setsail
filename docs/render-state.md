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
