#!/usr/bin/env python3
"""sudoku-validity: 3 constraint types x 2 shift-OOB lanes = 6 mask-collision
strips, reduced by a 6-flag AND aggregator.  Compacted successor of
build_lanes.py (same machine, tighter frame and much shorter dispatch pipes).

Encoding (chosen so no mask is ever 1<<63, which would be negative and flip the
strip's sign test -- bit 63 is unavoidable in a dense 0..81 packing):
    bit    = 9*idx + v          in 1..81
    shift1 = 63 - bit           lane1 = 1<<shift1  (nonzero iff bit <= 63, shift <= 62)
    shift2 = bit - 64 = ~shift1 lane2 = 1<<shift2  (nonzero iff bit >= 64, shift <= 17)
`{` returns 0 for a shift outside 0..63, so exactly one lane is nonzero per cell.
shift1+shift2 == -1, so shift2 is `1 N ~` off shift1 -- no second big constant.
shift1 = 63-9*idx-v is built as 9*(7-idx) - v: single digits only, no literal.

INPUT broadcasts five values per round: r, r/3, c, c/3, v.  Pre-dividing in
INPUT is what removes the box room's register wall (it never needs the divisor 3).

Layout facts that are load-bearing:
  * the six strip descending columns sit DIRECTLY under the six lane exits, so
    every mask pipe is a straight vertical drop and no two pipes cross;
  * each lane `s` is 7 cells nearer its own pipe than its sibling's (asserted);
  * DISPATCH sits above the MIDDLE addressing room.  The round's critical path is
    2 + 11 + L + 14 + 3 + 14 + 2 + 3 + 3 ticks, where L is the pipe to the
    FARTHEST addressing room; L dominates everything else that is tunable, and
    centring dispatch cuts it from 38 to 8.
"""
import sys, os
sys.path.insert(0, "/Users/visenbaev/icfpc26/tools")
from littleman import Program

# ---------------------------------------------------------------- ring helper
def ring_slots(W, H):
    """Op-cell coordinates, in execution order, of a perimeter loop occupying
    interior cols 1..W-1 / rows 0..H-1.  Corners are turn glyphs; '@' sits at
    (0,0) and feeds the top-left corner heading east, so the loop never re-enters
    '@' (which is not a valid instruction)."""
    s = [(x, 0) for x in range(2, W - 1)]
    s += [(W - 1, y) for y in range(1, H - 1)]
    s += [(x, H - 1) for x in range(W - 2, 1, -1)]
    s += [(1, y) for y in range(H - 2, 0, -1)]
    return s

def ring(p, x0, y0, W, H, ops):
    slots = ring_slots(W, H)
    assert len(ops) <= len(slots), (len(ops), len(slots))
    p.put(x0, y0, "@")
    p.put(x0 + 1, y0, ">")
    p.put(x0 + W - 1, y0, "v")
    p.put(x0 + W - 1, y0 + H - 1, "<")
    p.put(x0 + 1, y0 + H - 1, "^")
    pos = []
    for i, (dx, dy) in enumerate(slots):
        p.put(x0 + dx, y0 + dy, ops[i] if i < len(ops) else " ")
        pos.append((x0 + dx, y0 + dy))
    return pos

# ------------------------------------------------------------------ op streams
DISPATCH_OPS = list("3MrS/S3MrS/SrS")        # broadcast r, r/3, c, c/3, v

def addr_ops(pre, discard_after):
    return pre + list("M7-M9*M") + ["r"] * discard_after + list("rN+M1{s1N~M1{s")

ROW_OPS = addr_ops(["r"], 3)                 # idx = r  ; discard r/3, c, c/3
COL_OPS = addr_ops(["r", "r", "r"], 1)       # discard r, r/3 ; idx = c ; discard c/3
BOX_OPS = (list("rrM3*Mrr+M") + list("7-M9*M")
           + list("rN+M1{s1N~M1{s"))         # idx = 3*(r/3) + c/3
AGG_OPS = list("rM") + list("r&M") * 4 + list("r&s")

STRIP = ["v<", "vs", "r1", "bM", "~~", "-N", "aX", "~0", ">X", " s", " H"]

def strip(p, x, y):
    for j, row in enumerate(STRIP):
        for i, ch in enumerate(row):
            if ch != " ":
                p.put(x + i, y + j, ch)

# --------------------------------------------------------------------- layout
YG = 22
COLS = [8, 15, 23, 30, 38, 45]               # == the six lane-exit columns
EXITS = {"row": ((15, 17), (8, 17)), "col": ((30, 17), (23, 17)),
         "box": ((45, 18), (38, 18))}

def build():
    p = Program()

    p.input_room(16, 0)
    p.room(22, 0, 10, 6)
    ds = ring(p, 23, 1, 8, 4, DISPATCH_OPS)
    p.pipe([(19, 1), (21, 1)])

    p.room(5, 8, 14, 11);  rw = ring(p, 6, 9, 12, 9, ROW_OPS)
    p.room(20, 8, 14, 11); cl = ring(p, 21, 9, 12, 9, COL_OPS)
    p.room(35, 8, 16, 12); bx = ring(p, 36, 9, 14, 10, BOX_OPS)

    p.pipe([(21, 4), (17, 4), (17, 7)])       # dispatch -> ROW
    p.pipe([(26, 6), (26, 7)])                # dispatch -> COL
    p.pipe([(32, 4), (36, 4), (36, 7)])       # dispatch -> BOX

    p.room(3, YG, 45, 15)
    p.text(4, YG + 2, "@1NM")                 # shared init: B = -1 (all bits free)
    for k, X in enumerate(COLS):
        strip(p, X, YG + 3)
        if k < len(COLS) - 1:                 # 5 Y-forks make 6 men
            p.put(X, YG + 2, "Y")
            p.put(X, YG + 1, ">")
            p.put(X + 1, YG + 1, "v")
            p.put(X + 1, YG + 2, ">")
    p.put(COLS[-1], YG + 2, "v")              # the surviving man walks into strip 5
    for X, sy in zip(COLS, (19, 19, 19, 19, 20, 20)):
        p.pipe([(X, sy), (X, YG - 1)])

    p.room(15, 39, 12, 7); ag = ring(p, 16, 40, 10, 5, AGG_OPS)
    p.pipe([(20, YG + 15), (20, 38)])
    p.output_room(10, 43)
    p.pipe([(14, 44), (13, 44)])

    return p, dict(dispatch=ds, row=rw, col=cl, box=bx, agg=ag)

def check(ck):
    """Every lane `s` must sit directly above its own pipe: rebinding is silent."""
    ops = {"row": ROW_OPS, "col": COL_OPS, "box": BOX_OPS}
    for name, want in EXITS.items():
        idx = [i for i, c in enumerate(ops[name]) if c == "s"]
        got = tuple(ck[name][i] for i in idx)
        assert got == want, (name, got, want)
    for (x, _), c in zip([e for pair in EXITS.values() for e in pair],
                         [COLS[1], COLS[0], COLS[3], COLS[2], COLS[5], COLS[4]]):
        assert x == c, (x, c)

if __name__ == "__main__":
    p, ck = build()
    check(ck)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lanes2.man")
    p.save(out)
    print(out, "footprint", p.footprint())
