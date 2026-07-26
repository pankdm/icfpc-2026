#!/usr/bin/env python3
"""Build a vertical-P1 program with a parameterised DISP block."""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SOL = os.path.join(ROOT, "solutions", "history-lesson")
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, SOL)

from littleman import Program           # noqa: E402
import build_ring as base               # noqa: E402
import build_vertical_p1 as p1          # noqa: E402
from exp import encoding                # noqa: E402

TAIL = 66


def build(disp_rows, stream_row, disp_y=None, ring_pipes=None, unpack_x=74):
    """stream_row: index into disp_rows of the row holding the stream `r`."""
    _, ring, bands = encoding()
    program = Program()
    base.variable_feeder(program, bands, p1.WIDTH)
    tail = TAIL
    p1.place_vertical_p1(program, 0, tail, ring)

    dy = tail + 9 if disp_y is None else disp_y
    dh = len(disp_rows) + 2
    base.paste_room(program, 56, dy, disp_rows)
    base.paste_room(program, 56, tail, base.DECODER_ROWS)
    base.paste_room(program, 69, tail, base.UNPACK_ROWS)
    program.output_room(69, tail + 6)

    stream_y = dy + 1 + stream_row

    # feeder -> DECODER
    program.pipe([(55, tail), (55, tail + 2)], end_direction="E")
    # DECODER -> DISP (west wall, aligned with the classifier's stream `r`)
    program.pipe([
        (61, tail + 4),
        (61, tail + 8),
        (54, tail + 8),
        (54, stream_y),
        (55, stream_y),
    ], end_direction="E")
    # DISP -> UNPACK (north wall)
    program.pipe([
        (unpack_x, dy - 1),
        (unpack_x, tail + 5),
        (79, tail + 5),
        (79, tail + 4),
    ], end_direction="N")
    # UNPACK -> output
    program.pipe([
        (73, tail + 4),
        (73, tail + 5),
        (70, tail + 5),
    ], end_direction="S")

    if ring_pipes is None:
        assert dy + dh == tail + 20, (dy, dh)
        ring_pipes = [
            # P1 -> DISP: under both rooms, arriving at DISP's south wall.
            ([(52, tail + 16), (53, tail + 16), (53, tail + 22),
              (76, tail + 22), (76, tail + 21), (54, tail + 21),
              (54, tail + 20), (74, tail + 20)], "N"),
            # DISP -> P1
            ([(78, tail + 20), (78, tail + 23), (40, tail + 23),
              (40, tail + 20)], "N"),
        ]
    for path, end in ring_pipes:
        program.pipe(path, end_direction=end)

    bad = base.audit_vertical_ticks(program)
    assert not bad, f"vertical tick audit failed: {bad[:4]}"
    return program


def grade(program, name):
    out = os.path.join(HERE, name)
    program.save(out)
    res = subprocess.run(
        [sys.executable, os.path.join(ROOT, "tools", "grade_fast.py"),
         "history-lesson", out],
        capture_output=True, text=True)
    return program.footprint(), (res.stdout.strip() or res.stderr.strip())


if __name__ == "__main__":
    prog = build(p1.DISP_DELAYED_ROWS, stream_row=4)
    print(grade(prog, "baseline.man"))
