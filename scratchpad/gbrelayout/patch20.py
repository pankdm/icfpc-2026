#!/usr/bin/env python3
"""Two more travel trims.

1. AVG's accumulator is pinned west only by R2's READ band (12-17); its whole
   13-op chain fits starting at col 15 instead of 12, so the descent moves to
   col 14 and both the row-32 westbound leg and the row-39 eastbound leg lose
   two cells.  Bands after the shift: r(R2)@15, s(R2)@17, r(R3)@20, s(R3)@22.
   -4 cells x48 = -192.

2. SET's return climbs col 36 all the way to row 7, then runs west along row 7
   to (27,7) and drops onto row 8 -- but row 8 IS the westbound dispatch lane
   from col 27 on.  Stop the climb at row 8.  -10 cells x6 = -60.
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


# 1. accumulator: descend at col 14, chain starts at col 15
clr(12, 32, "v"); put(14, 32, "v")
clr(12, 38, "<"); clr(11, 38, "v"); clr(11, 39, ">")
put(14, 38, "<"); put(13, 38, "v"); put(13, 39, ">")
for x, ch in ((12, "r"), (15, "+"), (24, "7"), (25, "M"), (26, "1"), (27, "{"), (28, "W")):
    clr(x, 39, ch)
for x, ch in ((15, "r"), (16, "+"), (23, "7"), (24, "M"), (25, "1"), (26, "{"), (27, "W")):
    put(x, 39, ch)

# 2. SET's return leaves the col-36 rail one row earlier
put(36, 8, "<")

open(dst, "w").write("\n".join("".join(r).rstrip() for r in rows))
print("wrote", dst)
