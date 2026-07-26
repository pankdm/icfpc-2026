#!/usr/bin/env python3
"""sudoku-validity: lanes5 with the walking timer replaced by a backpack counter.

lanes5's timer was a 2-row ring plus a gap excursion -- ~70 cells of path to make
a 70-tick lap, which pinned two whole rows across the gadget's full width.
bptimer.py buys the same lap from BP instead of from path (lap = 4N+18 in a
5x9 block), so it fits a gap BETWEEN two strips and those two rows disappear:
the gadget goes 16 rows -> 14.

Frame is unchanged at 37x37 (width is binding, height only falls 37 -> 35), so
this is a score-neutral swap TODAY.  It is worth landing anyway because it is
what unlocks the next step: with the timer no longer needing rows of its own,
swapping the 2-col/10-row strips for the verified 3-col/7-row mask-zero-top
shortens the gadget to 11 rows, and the frame can then rebalance to ~34x34.
"""
import os, sys
sys.path.insert(0, "/Users/visenbaev/icfpc26/tools")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from littleman import Program
from build_lanes2 import DISPATCH_OPS, ROW_OPS, COL_OPS, BOX_OPS
from build_lanes3 import strip
import serp, bptimer

RW, RH = 9, 5
BW, BH = 11, 5
DW, DH = 10, 3
YA, YG = 7, 16
BOXX, ROWX, COLX = 0, 14, 26
TIMER_COL, TIMER_N = 12, 13        # block spans cols 11..15, lap = 4*13+18 = 70

def build(n=TIMER_N):
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

    p.pipe([(11, 3), (9, 3), (9, YA - 1)])
    p.pipe([(18, DH + 2), (18, YA - 1)])
    p.pipe([(24, 3), (28, 3), (28, YA - 1)])

    lanes = []
    for pos, ops in ((bx, BOX_OPS), (rw, ROW_OPS), (cl, COL_OPS)):
        lanes += [pos[i][0] for i, c in enumerate(ops) if c == "s"]
    cols = sorted(lanes)
    srcy = YA + RH + 2

    p.room(0, YG, cols[-1] + 3, 14)          # 14 rows: interior y17..y28
    p.text(1, YG + 2, "@1NM")
    chain = sorted(cols[:-1] + [TIMER_COL - 1])   # timer forks off at col 11
    for X in chain:
        p.put(X, YG + 2, "Y"); p.put(X, YG + 1, ">")
        p.put(X + 1, YG + 1, "v"); p.put(X + 1, YG + 2, ">")
    p.put(cols[-1], YG + 2, "v")
    for X in cols:
        strip(p, X, YG + 3)                  # strips occupy y19..y28
    for X in cols:
        p.pipe([(X, srcy), (X, YG - 1)])

    bptimer.place(p, TIMER_COL, YG + 3, n)   # block y19..y27, cols 11..15

    p.pipe([(18, YG + 14), (18, YG + 15)])
    p.output_room(17, YG + 16)
    return p, dict(cols=cols, row=rw, col=cl, box=bx)

def check(ck):
    cols = ck["cols"]
    assert len(set(cols)) == 6 and all(b - a >= 2 for a, b in zip(cols, cols[1:])), cols
    # the timer block (cols 11..15) must not collide with any 2-wide strip
    used = {c for X in cols for c in (X, X + 1)}
    assert not (used & set(range(TIMER_COL - 1, TIMER_COL + 4))), (cols, used)
    ops = {"row": ROW_OPS, "col": COL_OPS, "box": BOX_OPS}
    for name in ops:
        xs = [ck[name][i][0] for i, c in enumerate(ops[name]) if c == "s"]
        assert abs(xs[0] - xs[1]) >= 2, (name, xs)
        for x in xs:
            assert sorted(cols, key=lambda c: (abs(x - c), c))[0] in xs, (name, x)

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else TIMER_N
    p, ck = build(n)
    check(ck)
    name = sys.argv[2] if len(sys.argv) > 2 else "lanes6.man"
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
    p.save(out)
    print(out, "footprint", p.footprint(), "cols", ck["cols"], "LAP", bptimer.lap(n))
