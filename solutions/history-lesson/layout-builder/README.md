# History Lesson vertical-P1 layout builder

This directory contains a deliberately pipe-free geometry scaffold. It reuses
the encoding and optimized feeder from `../build_vertical_p1.py`, places a
fixed-width vertical dictionary below the feeder, and puts DECODER, UNPACK,
the output room, and delayed DISP side-by-side to its right.

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

The dictionary room's right wall is aligned with the feeder's right wall.
Within the room, every paired literal band is independently right-aligned.
`--dictionary-words` accepts 38 through 91 entries under the current base-92
protocol. The default 44-word setting preserves the current candidate's tuned
selection and physical order. Other values rerun phrase selection and feeder
encoding before laying out the resulting dictionary.

Dictionary constants are packed by a dynamic program. It first minimizes the
number of paired bands, then maximizes the number of constants in earlier
bands, and finally minimizes unused band width. After the last constant, the
loader sends the zero sentinel and enters the `r`/`s` buffer iteration loop;
the loop remains physically and semantically at the end of the preload path.

The generated `.man` is not a runnable solution. It has no pipes by design,
so its `r` and `s` instructions would fail if executed. Pipe attachment and
routing are a later phase.
