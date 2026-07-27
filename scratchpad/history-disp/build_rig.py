#!/usr/bin/env python3
"""Standalone rig for the route-B dispatcher: a real .man with real pipes.

Deliberately roomy -- the point is to get the classifier *working* first, with
no column pressure, and compact it afterwards.  The rig is:

    I --stream--> DISP --result--> O
                  DISP <--ring--> PUMP     (PUMP preloads, then r/s forever)

DISP classifies each stream symbol exactly as the real one must:

    v == 0          -> forward 0                (YEAR's job in the real build)
    1 <= v <= 16    -> ring position v
    v == 29         -> ESC: next symbol is the position
    60 <= v <= 65   -> ring position v - 43     (recycled run -> positions 17..22)
    otherwise       -> literal byte v + 31

Ring entry at position p holds 1000 + p, so a lookup is checkable by eye.

    python3 build_rig.py            # writes rig.man and prints the case JSON
"""
from __future__ import annotations

import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))
from littleman import Program                                  # noqa: E402

NPOS = 25            # ring positions 1..NPOS, then a 0 sentinel
DX, DY = 2, 2        # DISP room top-left
DW, DH = 40, 8       # DISP room size  (interior 38 x 6)


def disp_rows():
    """Interior of DISP: 38 columns x 6 rows, index-addressed."""
    w, h = 38, 6
    cells = [[" "] * w for _ in range(h)]

    def put(x, y, text):
        for i, ch in enumerate(text):
            assert cells[y][x + i] == " ", f"collision x={x+i} y={y} {ch!r}"
            cells[y][x + i] = ch

    # r0  return corridor.  x4 `s` is the only send to the output.
    #     x10 catches the zero path, x23 the literal-byte path, x36 the
    #     dictionary path coming off the sentinel riser.
    put(0, 0, "v@<<s")
    put(10, 0, "<"); put(23, 0, "<"); put(36, 0, "<")

    # r1  head: A=17, B=17, A=v (stream r), BP=v, zero test.
    #     x14.. is the in-range tail: rebuild BP = v-43 from B = 59-v.
    put(0, 1, ">`17`Mr bX^")
    put(14, 1, ">WM`16`-b"); put(25, 1, "v")

    # r2  the test.  x9's `-` is shared with the classifier descent: arriving
    #     with A=59 and B=v it computes 59-v for free.
    put(1, 2, ">`59`"); put(9, 2, "-M7+*X>")
    #     byte tail: rebuild v+31 = 90 - (59-v), then rise to the corridor.
    put(16, 2, "WM`90`-^")
    put(36, 2, "W")                       # sentinel riser: swap entry into A

    # r3  classifier and ESC test.  x13 drops the v<=16 lane, x14/x15 fold the
    #     byte lane's A>0 branch back up onto row 2.
    put(0, 3, "vX~`92`M+X")
    put(13, 3, "v>^")
    put(36, 3, "s")                       # sentinel riser: send the sentinel

    # r4  ESC lane (`r` then `b`), its eastward corridor, and the ring top.
    put(0, 4, ">rb")
    put(13, 4, ">"); put(25, 4, ">")
    put(26, 4, "> mdrMs>rX^")

    # r5  ring undersides.
    put(26, 5, "^sr<"); put(33, 5, "^s<")

    return ["".join(r) for r in cells]


def build():
    p = Program()
    rows = disp_rows()
    DX, DY = 10, 10                       # DISP room x10..x49, y10..y17
    p.room(DX, DY, 40, 8)
    for dy, row in enumerate(rows):
        for dx, ch in enumerate(row):
            if ch != " ":
                p.put(DX + 1 + dx, DY + 1 + dy, ch)

    # PUMP: one long preload row, then the six-cell r/s pump at its east end.
    px, py = 55, 24
    vals = [1000 + i for i in range(1, NPOS + 1)] + [0]
    cells = ["@"]
    for v in vals:
        cells += ["`", *str(v), "`", "s"]
    e = 1 + len(cells)                    # first free interior column
    p.room(px, py, e + 4, 5)
    for i, ch in enumerate(cells):
        p.put(px + 1 + i, py + 3, ch)
    p.put(px + e, py + 3, "^"); p.put(px + e, py + 2, "r")
    p.put(px + e, py + 1, ">"); p.put(px + e + 1, py + 1, "v")
    p.put(px + e + 1, py + 2, "s"); p.put(px + e + 1, py + 3, "<")

    p.input_room(0, 11)                   # x0..x2, y11..y13
    p.output_room(13, 5)                  # x13..x15, y5..y7

    # I -> DISP west wall, level with the head's `r`
    p.pipe([(3, 12), (9, 12)], end_direction="E")
    # DISP north wall (interior x=4) -> O
    p.pipe([(15, 9), (15, 8)], end_direction="N")
    # DISP east wall row 5 -> PUMP north wall.  The two ring legs run parallel
    # in the corridor east of DISP rather than crossing.
    p.pipe([(50, 16), (53, 16), (53, 23), (px + 2, 23)], end_direction="S")
    # PUMP north wall -> DISP east wall row 4
    p.pipe([(px + 6, 23), (px + 6, 15), (50, 15)], end_direction="W")
    return p


def case(n=600, seed=5):
    """Random mix, but force-feed the values that actually decide correctness:
    the product's zeros (59 and 66, both literal bytes), the run's own ends
    (60 and 65), the classifier threshold's neighbours (16, 18) and the zero
    marker."""
    rnd = random.Random(seed)
    stream, want = [], []

    def emit(v):
        stream.append(v)
        if v == 0:
            want.append(0)
        elif v <= 16:
            want.append(1000 + v)
        elif 60 <= v <= 65:
            want.append(1000 + v - 43)
        else:
            want.append(v + 31)

    for v in (0, 16, 18, 59, 60, 61, 64, 65, 66, 67, 91, 1):
        emit(v)
    for _ in range(n):
        c = rnd.random()
        if c < 0.08:
            emit(0)
        elif c < 0.32:
            emit(rnd.randint(1, 16))
        elif c < 0.55:
            emit(rnd.randint(60, 65))
        elif c < 0.72:
            emit(rnd.choice([16, 18, 59, 66, 58, 67]))
        elif c < 0.85:
            k = rnd.randint(17, NPOS); stream += [29, k]; want.append(1000 + k)
        else:
            emit(rnd.choice([x for x in range(18, 92)
                             if x != 29 and not 60 <= x <= 65]))
    return stream, want


if __name__ == "__main__":
    prog = build()
    out = os.path.join(HERE, "rig.man")
    prog.save(out)
    print(f"wrote {out}: {prog.footprint()}")
    s, w = case()
    with open(os.path.join(HERE, "rig_case.json"), "w") as fh:
        json.dump([{"in": [str(x) for x in s], "out": [str(x) for x in w]}], fh)
    print(f"case: {len(s)} symbols -> {len(w)} outputs")
