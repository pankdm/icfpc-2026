#!/usr/bin/env python3
"""sudoku-validity PoC: 3 constraint types x 2 shift-OOB lanes = 6 mask-collision
strips, reduced by a 6-flag AND aggregator.

Encoding (chosen so no mask is ever 1<<63, which would be negative and flip the
strip's sign test):
    bit    = 9*idx + v          in 1..81
    shift1 = 63 - bit           lane1 = 1<<shift1  (nonzero iff bit <= 63, shift <= 62)
    shift2 = bit - 64 = ~shift1 lane2 = 1<<shift2  (nonzero iff bit >= 64, shift <= 17)
`{` returns 0 for a shift outside 0..63, so exactly one lane is nonzero per cell.
shift1+shift2 == -1, so shift2 is `1 N ~` off shift1 -- no second big constant.
shift1 = 63-9*idx-v is built as 9*(7-idx) - v: single digits only, no literal.

INPUT room broadcasts five values per round: r, r/3, c, c/3, v.  Pre-dividing in
INPUT is what removes the box room's register wall (it never needs the divisor 3).
"""
import sys, os
sys.path.insert(0, "/Users/visenbaev/icfpc26/tools")
from littleman import Program

# ---------------------------------------------------------------- ring helper
def ring_slots(W, H):
    """Op-cell coordinates, in execution order, of a perimeter loop occupying
    interior cols 1..W-1 / rows 0..H-1.  Corners are turn glyphs, '@' sits at
    (0,0) and feeds the top-left corner heading east."""
    s = [(x, 0) for x in range(2, W - 1)]
    s += [(W - 1, y) for y in range(1, H - 1)]
    s += [(x, H - 1) for x in range(W - 2, 1, -1)]
    s += [(1, y) for y in range(H - 2, 0, -1)]
    return s

def ring(p, x0, y0, W, H, ops):
    """Draw the room's interior loop at interior origin (x0,y0). Returns the
    absolute coordinate of every op, indexed as given."""
    slots = ring_slots(W, H)
    assert len(ops) <= len(slots), (len(ops), len(slots))
    p.put(x0, y0, "@")
    p.put(x0 + 1, y0, ">")
    p.put(x0 + W - 1, y0, "v")
    p.put(x0 + W - 1, y0 + H - 1, "<")
    p.put(x0 + 1, y0 + H - 1, "^")
    pos = []
    for i, (dx, dy) in enumerate(slots):
        ch = ops[i] if i < len(ops) else " "
        p.put(x0 + dx, y0 + dy, ch)
        pos.append((x0 + dx, y0 + dy))
    return pos

# ------------------------------------------------------------------- programs
DISPATCH = list("3Mr S/S3Mr S/Sr S".replace(" ", ""))   # 3 M r S / S 3 M r S / S r S

def addr_ops(pre, post_idx):
    """pre  : reads before idx lands in A.  post_idx: reads to discard after."""
    return pre + list("M7-M9*M") + ["r"] * post_idx + list("rN+M1{s1N~M1{s")

ROW_OPS = addr_ops(["r"], 3)                      # idx = r ; then discard a,c,d
COL_OPS = addr_ops(["r", "r", "r"], 1)            # discard r,a ; idx = c ; discard d
BOX_OPS = (list("rrM3*Mr") + list("r+M") + list("7-M9*M")
           + list("rN+M1{s1N~M1{s"))              # discard r; a; discard c; d
AGG_OPS = list("rM") + list("r&M") * 4 + list("r&s")

STRIP = ["v<", "vs", "r1", "bM", "~~", "-N", "aX", "~0", ">X", " s", " H"]

def strip(p, x, y):
    for j, row in enumerate(STRIP):
        for i, ch in enumerate(row):
            if ch != " ":
                p.put(x + i, y + j, ch)

# --------------------------------------------------------------------- layout
YA = 14          # top wall row of the addressing band
YG = 29          # top wall row of the gadget room

def build():
    p = Program()
    checks = []

    # --- I room + dispatch --------------------------------------------------
    p.input_room(0, 4)
    p.room(5, 4, 8, 8)
    d = ring(p, 6, 5, 6, 6, DISPATCH)
    p.pipe([(3, 5), (4, 5)])

    # --- addressing rooms ---------------------------------------------------
    p.room(5, YA, 14, 11)                        # ROW  interior 12x9 @ (6,15)
    rw = ring(p, 6, YA + 1, 12, 9, ROW_OPS)
    p.room(20, YA, 14, 11)                       # COL  interior 12x9 @ (21,15)
    cl = ring(p, 21, YA + 1, 12, 9, COL_OPS)
    p.room(35, YA, 16, 12)                       # BOX  interior 14x10 @ (36,15)
    bx = ring(p, 36, YA + 1, 14, 10, BOX_OPS)

    p.pipe([(10, 12), (10, 13)])                 # dispatch -> ROW
    p.pipe([(13, 7), (26, 7), (26, 13)])         # dispatch -> COL
    p.pipe([(13, 5), (42, 5), (42, 13)])         # dispatch -> BOX

    # --- gadget room --------------------------------------------------------
    # strip descending columns sit directly under the six lane exits
    cols = [8, 15, 23, 30, 38, 45]
    p.room(3, YG, 45, 15)                        # interior x4..46, y30..42
    p.text(4, YG + 2, "@1NM")                    # shared init: B = -1
    for k, X in enumerate(cols):
        strip(p, X, YG + 3)
        if k < len(cols) - 1:                    # 5 forks make 6 men
            p.put(X, YG + 2, "Y")
            p.put(X, YG + 1, ">")
            p.put(X + 1, YG + 1, "v")
            p.put(X + 1, YG + 2, ">")
    p.put(cols[-1], YG + 2, "v")                 # last man turns into strip 5

    for src_y, X in [(25, 8), (25, 15), (25, 23), (25, 30), (26, 38), (26, 45)]:
        p.pipe([(X, src_y), (X, YG - 1)])

    # --- aggregator + O -----------------------------------------------------
    p.room(16, 46, 9, 9)                         # interior 7x7 @ (17,47)
    ag = ring(p, 17, 47, 7, 7, AGG_OPS)
    p.pipe([(20, YG + 15), (20, 45)])            # gadget -> AGG
    p.output_room(19, 57)
    p.pipe([(20, 55), (20, 56)])

    checks = dict(dispatch=d, row=rw, col=cl, box=bx, agg=ag, cols=cols)
    return p, checks

if __name__ == "__main__":
    p, ck = build()
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "poc1.man")
    p.save(out)
    print(out, "footprint", p.footprint())
    for name in ("row", "col", "box"):
        pos = ck[name]
        idx = [i for i, c in enumerate({"row": ROW_OPS, "col": COL_OPS, "box": BOX_OPS}[name]) if c == "s"]
        print(name, "s ops at", [pos[i] for i in idx])
