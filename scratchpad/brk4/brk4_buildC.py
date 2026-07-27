#!/usr/bin/env python3
"""Prove C routes at interior 12x3 by substituting it into p6v1 in place of room3.

The re-lay, derived from C_spec.json (rows [9,1,10,9] -> [10,10,9]):

  old  row0  v s < _ 0 a q s N <          row1 holds only '}' at col 9
       row2  @ v X 5 M U b m ] x          x's bit0 branch goes NORTH through '}'
       row3  > U ^ _ 0 d q s } <

  new  row0  v s < _ 0 a q s N } <        '}' moves onto the westward run
       row1  @ v X 5 M U b m ] _ x        'x' shifts to col 10
       row2  > U ^ _ 0 d q s } _ <        '<' shifts to col 10

`x` still turns north into a '<' that heads west, and '}' is the first cell of
that westward run -- so the executed sequence is unchanged (a turn touches no
register).  The two spare columns pay for the shift.

Box grows here (19 wide) because p6v1's other rooms stay put; this run is a
ROUTING proof only -- the layout itself is what brk6 needs.

  python3 scratchpad/brk4/brk4_buildC.py <out.man>
"""
import sys

SRC = "/Users/visenbaev/icfpc26/solutions/brackets/p6v1.man"
out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/c3.man"

rows = [list(r) for r in open(SRC).read().split("\n")]
while rows and not "".join(rows[-1]).strip():
    rows.pop()
W = max(len(r) for r in rows) + 4
for r in rows:
    r.extend(" " * (W - len(r)))
while len(rows) < 20:
    rows.append([" "] * W)

# ---- erase the old C: room [5,11]..[16,16] ------------------------------
for y in range(11, 17):
    for x in range(5, 17):
        rows[y][x] = " "

NEW = [
    "vs< 0aqsN}<",
    "@vX5MUbm] x",
    ">U^ 0dqs} <",
]
IX, IY = 6, 12                      # interior origin (unchanged)
IW, IH = 12, 3
# room walls
for x in range(IX - 1, IX + IW + 1):
    rows[IY - 1][x] = "-"
    rows[IY + IH][x] = "-"
for y in range(IY - 1, IY + IH + 1):
    rows[y][IX - 1] = "|"
    rows[y][IX + IW] = "|"
for c in ((IX - 1, IY - 1), (IX + IW, IY - 1), (IX - 1, IY + IH), (IX + IW, IY + IH)):
    rows[c[1]][c[0]] = "+"
for j, line in enumerate(NEW):
    for i, ch in enumerate(line):
        if ch != " ":
            rows[IY + j][IX + i] = ch

# ---- pipes: top col 11 (unchanged), bottom col 11, right wall at row IY+1 --
rows[IY - 1][11] = "-"              # top attachment stays on the wall run
rows[IY + IH][11] = "-"
# top pipe cell above the wall (from P above) and bottom pipe cell below
rows[IY - 2][11] = "v"
rows[IY + IH + 1][11] = "^"
# right-hand pipe: attach on the right wall at the middle interior row
rows[IY + 1][IX + IW] = "|"
rows[IY + 1][IX + IW + 1] = "<"

open(out, "w").write("\n".join("".join(r).rstrip() for r in rows))
print("wrote", out, "interior %dx%d" % (IW, IH),
      "cells", sum(1 for l in NEW for ch in l if ch != " "))
