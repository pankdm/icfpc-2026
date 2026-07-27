# History Lesson raw-text layout builder

This directory builds the feeder, vertical dictionary, and service tail for a
raw-text History Lesson encoding. Dictionary selection is independent of the
older YEAR-room and vertical-P1 encoders: `dictionary_words.json` is generated
directly from the final bytes in `../icfp-history.txt`, with no year markers or
year-slot substitutions.

The dictionary sits below the feeder with its left wall aligned to the
feeder's. DECODER, UNPACK, the output room, and compact DISP follow it
horizontally. The first three service blocks touch; two routing columns before
DISP keep its west input clear of the output room's east corner.

The compact dispatcher is the 21×5 block from `../build_vertical_p2.py`; its
room is 23×7 including walls. The builder uses that block's stream and ring
port offsets in connected mode, since nearest-pipe binding makes those offsets
part of the dispatcher's semantics.

The current connected design point is 89×88:

```bash
python3 solutions/history-lesson/layout-builder/build.py --connect-pipes
```

Its three layout parameters are explicit:

```bash
python3 solutions/history-lesson/layout-builder/build.py \
  --feeder-width 81 \
  --dictionary-width 38 \
  --dictionary-words 24 \
  --connect-pipes
```

The dictionary room's left wall is aligned with the feeder's left wall.
Within the room, every paired literal band remains independently right-aligned.
`--dictionary-words` accepts 17 through 91 entries under the current base-92
protocol. Seventeen is the real minimum: positions 1–16 are direct references
and position 17 restores ASCII `"0"`, whose shifted symbol is reserved by
DISP. At budget 17 apostrophe remains direct in slot 8. Budget 18 repurposes
that slot for a phrase and adds an escaped apostrophe identity.

Each run first logs semantic choice order, including the residual occurrence
count at the moment each phrase was chosen and its final reference count. It
then logs the independently optimized physical packing order as
`slot: word -> references`; physical slot numbers are not selection ranks.
Every catalog budget round-trips against the complete 2,810-byte output before
layout. Regenerate the catalog deterministically with:

```bash
python3 solutions/history-lesson/layout-builder/generate_dictionary.py
```

Semantic phrase priority and physical ring order are separate. Direct phrases
are selected first. Escaped phrases are then selected iteratively from the
current residual stream: after each replacement, all candidates are recounted
and the highest non-overlapping occurrence count wins. Symbol saving and
literal width break ties. The JSON records both the selection-time occurrence
count and estimated source-cell gain.

For each requested room width, the builder audits several physical
permutations based on literal width and reference frequency, independently
within direct positions 1–16 and escaped positions 17 onward. It rewrites
every feeder reference to the winning order.

Skip that physical-order audit for faster exploratory builds with:

```bash
python3 solutions/history-lesson/layout-builder/build.py --no-order-search
```

This preserves catalog order and still validates encoding and packing, but can
produce a taller dictionary. Its default filename includes `-natural-order`
so it cannot overwrite the searched variant.

## Experimental 80×80 fold

`sweep_geometry.py` regenerates feeder layouts and tests pipe-free rectangle
packings. It does not treat older generated `.man` dimensions as current,
because those may use the removed year mapping:

```bash
python3 solutions/history-lesson/layout-builder/sweep_geometry.py \
  --words 42,48,52,56,60 \
  --feeder-widths 80 \
  --dictionary-widths 48,56,64,72,80 \
  --target 80
```

The occurrence-ordered catalog cannot fit all independent rooms in 80×80.
The separate `dictionary_words_layout_gain.json` catalog instead prioritizes
estimated feeder-cell saving minus literal-table cost. With 52 words, a
second experimental remap converts the selected feeder stream to base-64:
the 2,117 source symbols become 2,210 codes, but ten base-64 codes fit in a
signed literal. The exact regenerated feeder is therefore 80×64.

Build the resulting pipe-free geometry with:

```bash
python3 solutions/history-lesson/layout-builder/build.py \
  --feeder-width 80 \
  --dictionary-width 56 \
  --dictionary-words 52 \
  --dictionary-catalog \
    solutions/history-lesson/layout-builder/dictionary_words_layout_gain.json \
  --compact-alphabet \
  --fold-tail
```

This produces `layout-f80-d56-n52-folded-base64.man`, exactly 80×80:

- feeder: 80×64;
- dictionary: 56×16;
- service strip: 24×16;
- the strip includes the compact dispatcher, decoder, unpacker, output, and a
  reserved 21×5 unmapper room.

This file is a geometry prototype, not a runnable solution. The unmapper room
currently contains only `@H`, and pipe routing is deliberately rejected for
`--compact-alphabet`. A functional version must replace that placeholder with
the base-64-to-protocol decoder and route the six existing links plus the new
decoder-to-unmapper link without leaving the 80×80 box.

Dictionary constants are packed by nested dynamic programs. The outer DP
chooses how many sequential constants belong to each paired band. For every
candidate band, an inner DP chooses the top/bottom split and aligns real and
dummy literal slots at minimum width. No slot counts or row split are fixed.
The combined objective minimizes paired bands, maximizes constants in earlier
bands, and then minimizes unused width. The 2×4 pump shifts only the first
paired band four columns to the right. Later bands recover that space:
column 1 contains their stateful start/descent turns and blank column 2 is
the upward return lane. The fixed top-left control area is:

```text
>rsv
x<<<
```

The initial `@` is immediately to the right of that 2×4 area. During preload,
BP=0 makes each edge `x` turn into the next band. After the final constant,
the loader sends the zero sentinel, sets BP=1, turns north once, and glides up
the blank return lane. The same pump `x` then turns it north into the pump.

An unmatched slot in one half of a paired band is rendered as an unsent zero
literal. These zeroes are not dictionary entries, but they are still
load-bearing: aligned backticks can pair vertically as well as horizontally,
and blanking a dummy partner can create an invalid accidental vertical
literal.

There is no dedicated bridge row: every later paired band starts immediately
below the previous one. This shifts the dictionary contents up one row and
leaves any padding at the bottom, where later whole-layout compaction can
remove it more easily.

Without `--connect-pipes`, the generated `.man` is a geometry scaffold rather
than a runnable solution; its `r` and `s` instructions have no pipes.

## Connected mode

Pass `--connect-pipes` to generate a runnable version:

```bash
python3 solutions/history-lesson/layout-builder/build.py --connect-pipes
```

This moves DECODER, UNPACK, output, and DISP two rows below their pipe-free
positions, leaving the dictionary in place. It then adds six intentionally
spacious, non-optimized routes: the four streaming pipeline links and both
directions of the dictionary ring. Connected mode reserves at least two blank
footer rows, and automatically adds more when a very small dictionary would
otherwise end above DISP's south ports. Connected outputs receive a
`-connected` filename suffix by default.

Verify a connected default build with both interpreters:

```bash
python3 tools/grade_fast.py history-lesson \
  solutions/history-lesson/layout-builder/layout-f81-d38-n24-connected.man
node tools/grade.js history-lesson \
  solutions/history-lesson/layout-builder/layout-f81-d38-n24-connected.man
```
