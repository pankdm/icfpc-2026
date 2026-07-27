#!/usr/bin/env python3
"""ALIGN rings: 8 cells -> 6.  `r` and `s` can share a column.

Both align loops are drawn 4 wide x 2 tall: `> r s v` over `< _ _ X`.  But the
belt's in-band (29-37) and out-band (32-37) overlap, so `r` and `s` can sit in
the SAME column on the two rows, and the X can double as the north-turning
corner.  That is a 3x2 ring:

      > r v          the X's A>0 turn goes straight back to the `>`
      X s <          A<0 exits south, A==0 (a zero grade) takes the old
                     west detour, now two cells instead of three

AVG's align runs 185x and TOP's 88x on the heavy case: -2 cells each = -546.
"""
import sys

src, dst = sys.argv[1], sys.argv[2]
rows = [list(r) for r in open(src).read().split("\n")]
w = max(len(r) for r in rows)
for r in rows:
    r.extend(" " * (w - len(r)))


def put(x, y, ch):
    assert rows[y][x] == " ", "occupied (%d,%d)=%r" % (x, y, rows[y][x])
    rows[y][x] = ch


def clr(x, y, expect):
    assert rows[y][x] == expect, "expected %r at (%d,%d), got %r" % (expect, x, y, rows[y][x])
    rows[y][x] = " "


# --- AVG's align (rows 37/38), 4-wide at cols 30-33 -> 3-wide at 31-33 -----
clr(31, 37, "r"); put(31, 37, ">")      # loop turn
clr(32, 37, "s"); put(32, 37, "r")
clr(30, 38, "X"); put(30, 38, "^")      # zero-grade detour, now 2 cells
put(32, 38, "s")
put(31, 38, "X")
put(31, 39, "<")                        # sentinel exit rejoins (30,39)'<'

# --- TOP's align (rows 43/44), 4-wide at cols 33-36 -> 3-wide at 33-35 ----
clr(35, 43, "s"); put(35, 43, "v")
clr(36, 43, "v"); clr(36, 44, "<")
put(35, 44, "<"); put(34, 44, "s")

open(dst, "w").write("\n".join("".join(r).rstrip() for r in rows))
print("wrote", dst)
