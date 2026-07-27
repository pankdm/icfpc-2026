#!/usr/bin/env python3
"""sudoku-validity: lanes3 re-proportioned.  Box 2304 -> 2025, pure geometry.

The band was 46 wide x 12 tall against a 43-tall frame, i.e. width-bound with 5
rows of slack.  Re-solving each ring's aspect ratio spends that slack:

    ROW/COL  W=12,H=9 (outer 14x11)  ->  W=11,H=11 (outer 13x13)
    BOX      W=14,H=10 (outer 16x12) ->  W=13,H=12 (outer 15x14)

Both new shapes still satisfy the placement constraints
    W+H-5 <= i1 ,  2W+H-9 >= i2 ,  2W+2H-10 >= len(ops)
so the two lane `s` ops stay on the bottom edge, and -- the point -- they land on
the SAME interior columns as before (x=9 and x=2, 7 apart), so every r/s binding
is bit-for-bit identical.  The critical path is unchanged as well: BOX still has
16 ops + 1 corner before its `v` read and a 13-op + 1-corner tail after it.

Band 46x12 -> 43x14, frame 48x43 -> 45x45.  The timer cliff is re-bisected
anyway, because the dispatch->BOX pipe lost a cell.
"""
import os, sys
sys.path.insert(0, "/Users/visenbaev/icfpc26/tools")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from littleman import Program
from build_lanes2 import ring, DISPATCH_OPS, ROW_OPS, COL_OPS, BOX_OPS
from build_lanes3 import strip

# --- ring geometry: (interior W, H); exits are always interior x=9 and x=2 ----
RW, RH = 11, 11          # ROW / COL   outer 13x13
BW, BH = 13, 12          # BOX         outer 15x14
YA, YG = 8, 24           # addressing top wall, gadget top wall
ROWX, COLX, BOXX = 5, 19, 33
TIMER_COL, TIMER_LEFT = 40, 12

def exits(x0, y0, W, H):
    """(lane1, lane2) send cells of a ring at interior origin (x0,y0)."""
    return (x0 + 9, y0 + H - 1), (x0 + 2, y0 + H - 1)

def build(timer_left=TIMER_LEFT):
    p = Program()

    p.input_room(15, 0)
    p.room(21, 0, 10, 6)
    ring(p, 22, 1, 8, 4, DISPATCH_OPS)
    p.pipe([(18, 1), (20, 1)])

    p.room(ROWX, YA, RW + 2, RH + 2); rw = ring(p, ROWX + 1, YA + 1, RW, RH, ROW_OPS)
    p.room(COLX, YA, RW + 2, RH + 2); cl = ring(p, COLX + 1, YA + 1, RW, RH, COL_OPS)
    p.room(BOXX, YA, BW + 2, BH + 2); bx = ring(p, BOXX + 1, YA + 1, BW, BH, BOX_OPS)

    p.pipe([(20, 4), (16, 4), (16, YA - 1)])      # dispatch -> ROW
    p.pipe([(25, 6), (25, YA - 1)])               # dispatch -> COL
    p.pipe([(31, 4), (34, 4), (34, YA - 1)])      # dispatch -> BOX

    # six strip columns == the six lane-exit columns, so every mask pipe is a
    # straight vertical drop and no two pipes cross
    e = [exits(ROWX + 1, YA + 1, RW, RH), exits(COLX + 1, YA + 1, RW, RH),
         exits(BOXX + 1, YA + 1, BW, BH)]
    cols = [e[0][1][0], e[0][0][0], e[1][1][0], e[1][0][0], e[2][1][0], e[2][0][0]]
    srcy = [YA + RH + 2] * 4 + [YA + BH + 2] * 2

    p.room(3, YG, cols[-1], 16)               # interior x4.., y25..38
    p.text(4, YG + 2, "@1NM")
    for X in cols[:-1] + [TIMER_COL]:             # 6 Y-forks -> 7 men
        p.put(X, YG + 2, "Y"); p.put(X, YG + 1, ">")
        p.put(X + 1, YG + 1, "v"); p.put(X + 1, YG + 2, ">")
    p.put(cols[-1], YG + 2, "v")
    for X in cols:
        strip(p, X, YG + 3)                       # strips occupy y27..y36
    for X, sy in zip(cols, srcy):
        p.pipe([(X, sy), (X, YG - 1)])

    ty = YG + 13                                  # first free row under the strips
    p.put(TIMER_COL, ty, "<"); p.put(timer_left, ty, "v")
    p.put(timer_left, ty + 1, ">"); p.put(TIMER_COL, ty + 1, "^")
    p.put(timer_left + 2, ty + 1, "1"); p.put(timer_left + 3, ty + 1, "s")

    p.pipe([(20, YG + 16), (20, YG + 17)])
    p.output_room(19, YG + 18)
    return p, dict(row=rw, col=cl, box=bx, cols=cols)

def check(ck):
    """Every lane `s` must sit directly above its own strip column."""
    ops = {"row": ROW_OPS, "col": COL_OPS, "box": BOX_OPS}
    want = {"row": (ck["cols"][1], ck["cols"][0]), "col": (ck["cols"][3], ck["cols"][2]),
            "box": (ck["cols"][5], ck["cols"][4])}
    for name, cs in want.items():
        idx = [i for i, c in enumerate(ops[name]) if c == "s"]
        got = tuple(ck[name][i][0] for i in idx)
        assert got == cs, (name, got, cs)
    assert len(set(ck["cols"])) == 6 and ck["cols"] == sorted(ck["cols"])

if __name__ == "__main__":
    left = int(sys.argv[1]) if len(sys.argv) > 1 else TIMER_LEFT
    p, ck = build(left)
    check(ck)
    name = sys.argv[2] if len(sys.argv) > 2 else "lanes4.man"
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
    p.save(out)
    print(out, "footprint", p.footprint(), "cols", ck["cols"],
          "LAP", 2 * (TIMER_COL + 1 - left))
