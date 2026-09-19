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

## Candidates, and the reasoning

**`offset=28` (4x4) paired with `offset=12` (3x4)** is the strongest lead. The two have
*identical* call counts (2,536) and the same small number of distinct source buffers
(3), which means they are written together, from engine-owned storage that is reused
rather than allocated per object. `offset=32` (4x4) and `offset=16` (3x4) repeat the
pattern at 1,104 calls with 2 buffers — the same shape, a different shader family.

A plausible reading is a 3x4 model/world matrix beside a 4x4 view-projection, but that
is a hypothesis about a layout, **not** an identification. A small number of distinct
source buffers is equally consistent with a shared scratch buffer rewritten per draw.

By contrast `offset=0` (4x4) has 22 distinct source buffers across 2,809 calls, which
looks like per-object data rather than one camera.

## What would settle it

The values, which this run did not capture — the log records the source pointer, not the
contents. The discriminator is straightforward once values are in hand:

- a **camera** transform is identical across every draw within one flip, and changes
  between flips only when the viewpoint moves;
- an **object** transform differs between draws within the same flip.

Holding the camera still while objects move, and then moving only the camera, separates
them without any appeal to what the numbers look like. Recovering a matrix by eyeballing
floats for a plausible projection row is explicitly not the method: it guesses, and a
wrong guess produces a blend that looks nearly right.

## Limits of the current inventory

The run reached only the title's early stages, on the software rasteriser, for about two
minutes. The slot inventory is therefore **not** complete for the whole game: shader
families used later will add slots. Any policy built from this table must fail loudly on
an unknown slot rather than assume this list is exhaustive.
