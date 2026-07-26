# History Lesson vertical-P1 layout builder

This directory contains a deliberately pipe-free geometry scaffold. It reuses
the encoding and optimized feeder from `../build_vertical_p1.py`, places a
fixed-width vertical dictionary below the feeder with its left wall aligned
to the feeder's left wall. DECODER, UNPACK, the output room, and delayed DISP
follow it horizontally with touching walls and no empty columns between
blocks. Every tail room touches the feeder's bottom boundary and the complete
row extends to the right as far as necessary.

The default is the current `81x90-vertical-p1` design point:

```bash
python3 solutions/history-lesson/layout-builder/build.py
```

Its three layout parameters are explicit:

```bash
python3 solutions/history-lesson/layout-builder/build.py \
  --feeder-width 81 \
  --dictionary-width 52 \
  --dictionary-words 44
```

The dictionary room's left wall is aligned with the feeder's left wall.
Within the room, every paired literal band remains independently right-aligned.
`--dictionary-words` accepts 38 through 91 entries under the current base-92
protocol. The default 44-word setting preserves the current candidate's tuned
selection and physical order. Other values rerun phrase selection and feeder
encoding before laying out the resulting dictionary.

Dictionary constants are packed by nested dynamic programs. The outer DP
chooses how many sequential constants belong to each paired band. For every
candidate band, an inner DP chooses the top/bottom split and aligns real and
dummy literal slots at minimum width. No slot counts or row split are fixed.
The combined objective minimizes paired bands, maximizes constants in earlier
bands, and then minimizes unused width. The 2×4 pump shifts only the first
paired band four columns to the right. Later bands recover that space and
reserve only the leftmost column for the upward return (plus their normal
start/turn cells). The fixed top-left control area is:

```text
>rsv
^<<<
```

The initial `@` is immediately to the right of that 2×4 area. After the final
constant, the loader sends the zero sentinel and follows a column of `^`
instructions back to the pump.

A one-row bridge immediately below the first pair carries its column-5
descent west and down into the column-2 starts used by every later pair.

The builder may permute physical dictionary positions while keeping direct
entries in positions 1–16 and escaped entries after them. It rewrites feeder
references to match. At the default 52-column width this lets the DP attain
the minimum feasible band count without adding footer rows below the constants.

The generated `.man` is not a runnable solution. It has no pipes by design,
so its `r` and `s` instructions would fail if executed. Pipe attachment and
routing are a later phase.

## Connected mode

Pass `--connect-pipes` to generate a runnable version:

```bash
python3 solutions/history-lesson/layout-builder/build.py --connect-pipes
```

This moves DECODER, UNPACK, output, and DISP two rows below their pipe-free
positions, leaving the dictionary in place. It then adds six intentionally
spacious, non-optimized routes: the four streaming pipeline links and both
directions of the dictionary ring. Connected mode reserves two blank rows at
the bottom of the dictionary room for those routes; the compact pipe-free
room does not. Connected outputs receive a `-connected` filename suffix by
default. Routes may extend to the right, but the builder asserts that none
extends below the dictionary room's bottom boundary.

Verify a connected default build with both interpreters:

```bash
python3 tools/grade_fast.py history-lesson \
  solutions/history-lesson/layout-builder/layout-f81-d52-n44-connected.man
node tools/grade.js history-lesson \
  solutions/history-lesson/layout-builder/layout-f81-d52-n44-connected.man
```
