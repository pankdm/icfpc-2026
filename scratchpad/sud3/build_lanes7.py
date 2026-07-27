#!/usr/bin/env python3
"""sudoku-validity: 3-col/7-row mask-zero-top strips + narrower serpentine rooms.

lanes5 was 37x37 with the gadget 16 rows deep (2 fork rows + 10-row strips +
2 timer rows).  Swapping the 2-col/10-row mask-zero-2col for the verified
3-col/7-row mask-zero-top takes the gadget to 13 rows, which frees height -- but
height was NOT binding, so the rows only pay once the band narrows too:

    ROW/COL  W=9,H=5  (outer 11x7)  ->  W=8,H=7  (outer 10x9)
    BOX      W=11,H=5 (outer 13x7)  ->  W=9,H=7  (outer 11x9)
    band 37x7 -> 33x9,  frame 37x37 -> 34x36,  box 1369 -> 1296

Strip geometry: mask-zero-top's entry `>` is at local column 1, so a fork's
south copy lands on it travelling south and is turned east exactly as the
original init tail did.  The `r` sits at local column 2, so a strip fed by a
pipe dropping at column C occupies C-2..C with its Y at C-1.  Strips are 3 wide
now, so consecutive exit columns must be >=3 apart (was 2).

It is also faster: the duplicate reaches `s` 7 ticks after `r` instead of 8, and
a fresh mask costs 10 ticks instead of 12, so the timer cliff is re-bisected.
"""
import os, sys
sys.path.insert(0, "/Users/visenbaev/icfpc26/tools")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from littleman import Program
from build_lanes2 import DISPATCH_OPS, ROW_OPS, COL_OPS, BOX_OPS
import serp

# mask-zero-top, init tail stripped: local cols 0,1,2 / rows 0..6
STRIP3 = [" >v",
          " Mr",
          " ~b",
          "H &",
          "s^X",
          "^Xd",
          " ^<"]

RW, RH = 9, 5             # ROW / COL  outer 11x7
BW, BH = 9, 7             # BOX        outer 11x9
DW, DH = 10, 3            # dispatch   outer 12x5
YA = 7
BOXX, ROWX, COLX = 1, 13, 25
EXC = 16                  # free gap column pair for the timer excursion

def strip3(p, x, y):
    for j, row in enumerate(STRIP3):
        for i, ch in enumerate(row):
            if ch != " ":
                p.put(x + i, y + j, ch)

def build(timer_left=1, depth=0):
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
    srcb, srcr = YA + BH + 2, YA + RH + 2

    lanes = []
    for pos, ops in ((bx, BOX_OPS), (rw, ROW_OPS), (cl, COL_OPS)):
        lanes += [pos[i][0] for i, c in enumerate(ops) if c == "s"]
    cols = sorted(lanes)
    srcy = {c: (srcb if c in [bx[i][0] for i, ch in enumerate(BOX_OPS) if ch == "s"]
                else srcr) for c in cols}
    YG = srcb + 2                                  # gadget top wall

    # gadget: return row, fork row, 7 strip rows, 2 timer rows -> 13 outer
    p.room(0, YG, cols[-1] + 3, 13)
    R0, R1, R2 = YG + 1, YG + 2, YG + 3
    # init folded VERTICALLY: horizontal `@1NM` would sit 5 columns left of the
    # first strip and push the gadget 2 columns past the band (w 37, no gain).
    ix = cols[0] - 4
    p.put(ix, R0, "@"); p.put(ix + 1, R0, "v")
    for k, ch in enumerate("1NM>"):
        p.put(ix + 1, R1 + k, ch)
    p.put(ix + 2, R1 + 3, "^"); p.put(ix + 2, R1, ">")
    tfork = cols[-1] - 3                           # timer forks off a free column
    for C in [c - 1 for c in cols[:-1]] + [tfork]:
        p.put(C, R1, "Y"); p.put(C, R0, ">")
        p.put(C + 1, R0, "v"); p.put(C + 1, R1, ">")
    p.put(cols[-1] - 1, R1, "v")                   # survivor drops into the last strip
    for C in cols:
        strip3(p, C - 2, R2)
    for C in cols:
        p.pipe([(C, srcy[C]), (C, YG - 1)])

    ty = R2 + 7                                    # two timer rows under the strips
    tcol = tfork
    p.put(tcol, ty, "<"); p.put(timer_left, ty, "v")
    p.put(timer_left, ty + 1, ">"); p.put(tcol, ty + 1, "^")
    p.put(timer_left + 2, ty + 1, "1"); p.put(timer_left + 3, ty + 1, "s")
    if depth:
        p.put(EXC, ty + 1, "^"); p.put(EXC, ty + 1 - depth, ">")
        p.put(EXC + 1, ty + 1 - depth, "v"); p.put(EXC + 1, ty + 1, ">")

    p.pipe([(18, YG + 13), (18, YG + 14)])
    p.output_room(17, YG + 15)
    return p, dict(cols=cols, row=rw, col=cl, box=bx, lap=2 * (tcol - timer_left + 1))

EXC = 11

def check(ck):
    cols = ck["cols"]
    assert len(set(cols)) == 6, cols
    assert all(b - a >= 3 for a, b in zip(cols, cols[1:])), ("3-wide strips", cols)
    ops = {"row": ROW_OPS, "col": COL_OPS, "box": BOX_OPS}
    for name in ops:
        xs = [ck[name][i][0] for i, c in enumerate(ops[name]) if c == "s"]
        assert abs(xs[0] - xs[1]) >= 3, (name, xs)
        for x in xs:
            assert sorted(cols, key=lambda c: (abs(x - c), c))[0] in xs, (name, x)

if __name__ == "__main__":
    depth = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    p, ck = build(depth=depth)
    check(ck)
    name = sys.argv[2] if len(sys.argv) > 2 else "lanes7.man"
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
    p.save(out)
    print(out, "footprint", p.footprint(), "cols", ck["cols"],
          "LAP", ck["lap"] + 2 * depth)
