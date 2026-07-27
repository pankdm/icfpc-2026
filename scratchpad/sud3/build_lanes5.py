#!/usr/bin/env python3
"""sudoku-validity: dense serpentine rooms.  Box 2025 -> 1369.

lanes4 carried 90 ops in 548 cells of addressing room (~16% density) because a
ring only ever uses its perimeter -- the whole interior was dead.  Replacing the
rings with boustrophedon loops that fill the rectangle (serp.py) shrinks
ROW/COL to outer 11x7 and BOX to 13x7, and the frame from 45x45 to 37x37.

Two constraints relax on the way, which is what makes it fit:

* `s` binding no longer forces the lane sends onto the bottom edge.  Both lane
  pipes leave via the bottom wall, so the vertical term of the Manhattan
  distance is COMMON to both and binding reduces to |x_s - c1| < |x_s - c2|.
  Any two distinct exit columns work; they need only be >=2 apart so the 2-cell
  strips they feed do not overlap.

* room ORDER is free.  Putting BOX leftmost costs nothing and zeroes the gadget's
  init-tail overhang, because BOX's nearest exit sits 4 columns inside the room
  while ROW's sits 1 column in.

The critical path pays 4 ticks for the fold (BOX pre-v 17->20, tail 14->15) as
the serpentine crosses turn cells the ring did not, so the timer cliff is
re-bisected from scratch.
"""
import os, sys
sys.path.insert(0, "/Users/visenbaev/icfpc26/tools")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from littleman import Program
from build_lanes2 import DISPATCH_OPS, ROW_OPS, COL_OPS, BOX_OPS
from build_lanes3 import strip
import serp

RW, RH = 9, 5             # ROW / COL  outer 11x7
BW, BH = 11, 5            # BOX        outer 13x7
DW, DH = 10, 3            # dispatch   outer 12x5  (all `S`, so no binding needs)
YA, YG = 7, 16
BOXX, ROWX, COLX = 0, 14, 26
TIMER_COL, TIMER_LEFT = 31, 1
# The timer's lap must exceed one cell's processing time. A flat 2-row ring at
# this width tops out at 62 ticks, which is NOT enough, so the return leg makes
# one excursion up a free gap between strips: LAP = 62 + 2*EXC_DEPTH, tunable in
# steps of 2 without spending a single extra row of frame.
EXC_COL, EXC_DEPTH = 11, 6

def build(timer_left=TIMER_LEFT, depth=EXC_DEPTH):
    p = Program()

    p.input_room(0, 0)
    p.room(12, 0, DW + 2, DH + 2)
    serp.place(p, 13, 1, DW, DH, DISPATCH_OPS)
    p.pipe([(3, 1), (11, 1)])

    p.room(BOXX, YA, BW + 2, BH + 2)
    bx = serp.place(p, BOXX + 1, YA + 1, BW, BH, BOX_OPS)
    p.room(ROWX, YA, RW + 2, RH + 2)
    rw = serp.place(p, ROWX + 1, YA + 1, RW, RH, ROW_OPS)
    p.room(COLX, YA, RW + 2, RH + 2)
    cl = serp.place(p, COLX + 1, YA + 1, RW, RH, COL_OPS)

    p.pipe([(11, 3), (9, 3), (9, YA - 1)])         # dispatch -> BOX
    p.pipe([(18, DH + 2), (18, YA - 1)])           # dispatch -> ROW
    p.pipe([(24, 3), (28, 3), (28, YA - 1)])       # dispatch -> COL

    # lane exits: (room, ops, bottom-wall row of that room)
    lanes = []
    for pos, ops, h in ((bx, BOX_OPS, BH), (rw, ROW_OPS, RH), (cl, COL_OPS, RH)):
        idx = [i for i, c in enumerate(ops) if c == "s"]
        lanes += [pos[i][0] for i in idx]
    cols = sorted(lanes)
    srcy = YA + RH + 2                             # all three rooms share a height

    p.room(0, YG, cols[-1] + 3, 16)                # interior x1..x(cols[-1]+1)
    p.text(1, YG + 2, "@1NM")
    for X in cols[:-1] + [TIMER_COL]:              # 6 Y-forks -> 7 men
        p.put(X, YG + 2, "Y"); p.put(X, YG + 1, ">")
        p.put(X + 1, YG + 1, "v"); p.put(X + 1, YG + 2, ">")
    p.put(cols[-1], YG + 2, "v")
    for X in cols:
        strip(p, X, YG + 3)                        # strips occupy YG+3 .. YG+12
    for X in cols:
        p.pipe([(X, srcy), (X, YG - 1)])

    ty = YG + 13
    p.put(TIMER_COL, ty, "<"); p.put(timer_left, ty, "v")
    p.put(timer_left, ty + 1, ">"); p.put(TIMER_COL, ty + 1, "^")
    p.put(timer_left + 2, ty + 1, "1"); p.put(timer_left + 3, ty + 1, "s")
    if depth:                                      # detour up a strip-free gap
        p.put(EXC_COL, ty + 1, "^"); p.put(EXC_COL, ty + 1 - depth, ">")
        p.put(EXC_COL + 1, ty + 1 - depth, "v"); p.put(EXC_COL + 1, ty + 1, ">")

    p.pipe([(18, YG + 16), (18, YG + 17)])
    p.output_room(17, YG + 18)
    return p, dict(cols=cols, row=rw, col=cl, box=bx)

def check(ck):
    cols = ck["cols"]
    assert len(set(cols)) == 6, cols
    assert all(b - a >= 2 for a, b in zip(cols, cols[1:])), cols   # strips are 2 wide
    ops = {"row": ROW_OPS, "col": COL_OPS, "box": BOX_OPS}
    for name in ops:                                   # each `s` nearest its own pipe
        idx = [i for i, c in enumerate(ops[name]) if c == "s"]
        xs = [ck[name][i][0] for i in idx]
        assert abs(xs[0] - xs[1]) >= 2, (name, xs)
        for x in xs:
            d = sorted(cols, key=lambda c: (abs(x - c), c))
            assert d[0] in xs, (name, x, d[:2])

if __name__ == "__main__":
    left = TIMER_LEFT
    depth = int(sys.argv[1]) if len(sys.argv) > 1 else EXC_DEPTH
    p, ck = build(left, depth)
    check(ck)
    name = sys.argv[2] if len(sys.argv) > 2 else "lanes5.man"
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
    p.save(out)
    print(out, "footprint", p.footprint(), "cols", ck["cols"],
          "LAP", 2 * (TIMER_COL + 1 - left) + 2 * depth)
