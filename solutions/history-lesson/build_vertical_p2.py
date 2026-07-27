#!/usr/bin/env python3
"""Vertical-P1 build with a rebuilt dispatcher (DISP) room.

Everything outside DISP is `build_vertical_p1`: the same encoding, the same
variable-width feeder, the same tall P1 dictionary room.  Only the dispatcher
block -- the room holding the `17`, `31` and `92` literals -- is rebuilt, from
25x11 down to 23x7.

Three things shrank it:

* **The 81-lap countdown is gone.**  `build_vertical_p1` spends its top three
  rows on a delay loop meant to hold DISP off until P1 finishes its vertical
  preload.  It is not load-bearing: the two ring legs carry 118 cells against a
  44-entry dictionary, so DISP simply blocks on `r` while P1 is still loading.
  Removing the loop passes and is ~800 ticks faster.
* **`b` moved into the classifier head.**  Stashing the raw symbol in `BP`
  *before* subtracting 17 means the `v <= 16` branch already holds its rotation
  count, which deletes the `-` cell on its own row plus the `+`/`b` pair that
  used to rebuild the count -- three cells and, more usefully, two columns.
* **The sentinel return folded into a riser column.**  The old grid spent a
  whole sixth row walking west from the ring send back to the swap.  Testing
  the drained value with the `X` *before* it turns lets the sentinel fall out
  of the drain loop travelling east, so `s`/`W` stack vertically in the last
  column instead of spreading across a row.

Run `scratchpad/history-disp/simtest.py` to exercise the room's semantics on
its own; `docs`-level notes live in this directory's README.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))

from littleman import Program

import build_ring as base
import build_vertical_p1 as p1


TAIL = 66            # first row below the feeder
DISP_X = 56          # DISP's west wall
DISP_Y = TAIL + 13   # DISP's north wall; its south wall stays at TAIL+19
UNPACK_PORT = 76     # x of DISP's outgoing north-wall attachment
RING_OUT_PORT = 77   # x of DISP's outgoing south-wall attachment
RING_IN_PORT = 74    # x of DISP's incoming south-wall attachment


def _grid(width, height, *placements):
    """Index-addressed grid, so a miscounted run of spaces cannot silently
    shift a glyph.  placements are (x, y, text)."""
    cells = [[" "] * width for _ in range(height)]
    for x, y, text in placements:
        for i, glyph in enumerate(text):
            assert cells[y][x + i] == " ", (x + i, y, glyph)
            cells[y][x + i] = glyph
    return ["".join(row) for row in cells]


# The dispatcher, 21x5.  Registers on entry to row 1: A and B free, BP free.
#
#   row 0  return corridor; `s` at x=4 is the only send to UNPACK
#   row 1  head: A=17, B=17, A=symbol, BP=symbol, A=symbol-17, drop
#   row 2  the +31 path for raw ASCII symbols, and the sentinel riser
#   row 3  ESC test (`92` reads back as 29 westward), then the ring machinery
#   row 4  ESC's second stream read, slot-17 join, and both ring-loop undersides
#
# Ring machinery, x=10..20 of rows 3/4:
#   10..13  rotate BP-1 times: `>` ` ` `m` `d` over `^` `s` `r` `<`
#   14..16  take the wanted entry, keep it in B, put it back on the ring
#   17..19  drain the rest back until the 0 sentinel: `>` `r` `X` over `^` `s` `<`
#   20      sentinel riser: send the sentinel, `W` the entry into A, go home
DISP_ROWS = _grid(21, 5,
    (0, 0, "v@<"), (4, 0, "s"), (10, 0, "<"), (20, 0, "<"),
    (0, 1, ">`17`Mrb-v"), (20, 1, "W"),
    (1, 2, ">`31`+"), (10, 2, "^"), (20, 2, "s"),
    (0, 3, "vX~`92`M+X> mdrMs>rX^"),
    (0, 4, ">rb"), (9, 4, ">^sr<"), (17, 4, "^s<"),
)
DISP_STREAM_ROW = 1   # row of the head's stream `r`, which the west port faces


def build():
    _, ring, bands = p1.build_encoding()
    probe = Program()
    feeder_rows = base.variable_feeder(probe, bands, p1.WIDTH)
    assert feeder_rows == 64, feeder_rows
    assert feeder_rows + 2 == TAIL

    program = Program()
    base.variable_feeder(program, bands, p1.WIDTH)
    p1.place_vertical_p1(program, 0, TAIL, ring)
    base.paste_room(program, DISP_X, DISP_Y, DISP_ROWS)
    base.paste_room(program, DISP_X, TAIL, base.DECODER_ROWS)
    base.paste_room(program, 69, TAIL, base.UNPACK_ROWS)
    program.output_room(69, TAIL + 6)

    stream_y = DISP_Y + 1 + DISP_STREAM_ROW

    # feeder -> DECODER
    program.pipe([(55, TAIL), (55, TAIL + 2)], end_direction="E")
    # DECODER -> DISP, down the routing strip and into the head's `r`
    program.pipe([
        (61, TAIL + 4),
        (61, TAIL + 8),
        (54, TAIL + 8),
        (54, stream_y),
        (55, stream_y),
    ], end_direction="E")
    # DISP -> UNPACK.  x=76 rather than the old x=74: it has to lose a
    # nearest-pipe contest against the ring port at x=77 for the drain sends,
    # while still beating it for the single stream send on row 0.
    program.pipe([
        (UNPACK_PORT, DISP_Y - 1),
        (UNPACK_PORT, TAIL + 5),
        (79, TAIL + 5),
        (79, TAIL + 4),
    ], end_direction="N")
    # UNPACK -> output
    program.pipe([
        (73, TAIL + 4),
        (73, TAIL + 5),
        (70, TAIL + 5),
    ], end_direction="S")
    # P1 -> DISP, serpentined under both rooms
    program.pipe([
        (52, TAIL + 16),
        (53, TAIL + 16),
        (53, TAIL + 22),
        (76, TAIL + 22),
        (76, TAIL + 21),
        (54, TAIL + 21),
        (54, TAIL + 20),
        (RING_IN_PORT, TAIL + 20),
    ], end_direction="N")
    # DISP -> P1
    program.pipe([
        (RING_OUT_PORT, TAIL + 20),
        (RING_OUT_PORT, TAIL + 23),
        (40, TAIL + 23),
        (40, TAIL + 20),
    ], end_direction="N")

    bad = base.audit_vertical_ticks(program)
    assert not bad, f"vertical tick audit failed: {bad[:4]}"
    return program


def main():
    program = build()
    out = os.path.join(HERE, "candidates", "81x90-vertical-p2.man")
    program.save(out)
    width, height, score = program.footprint()
    print(f"wrote {out}: {width}x{height} score={score}")


if __name__ == "__main__":
    main()
