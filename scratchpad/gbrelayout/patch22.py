#!/usr/bin/env python3
"""Two last U-turns, for margin (we cleared the rank below by only 12,328).

1. TOP's sentinel exit sweeps row 54 west to col 7, drops a row and runs back
   east to its first op, `r`(R3) at col 18.  R3's read band is 18-23, so the
   pivot belongs at col 17.  -20 cells x2.

2. AVG's sentinel exit drops to row 41, runs west to col 24, jogs down to row
   43, runs west again to col 7 to reach a `-`, then climbs and runs east to
   (12,40).  The `-` at (7,42) is SHARED with dispatch stage 4 (count 5 = 3+2),
   so it cannot move -- but AVG can have its own at (12,41) and go straight:
   row 41 west to col 12, `-`, climb, `>` into r(R2) at col 12.  -11 cells x3.
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


# 1. TOP sentinel exit pivots at col 17
put(17, 54, "v")
put(17, 55, ">")

# 2. AVG's sentinel exit was going to be straightened along row 41 too, but
# MEASURED: cols 9-23 of row 41 carry AVG's OUTPUT path at the same count (3),
# so a turn there diverts it.  The sentinel path leaves row 41 at col 24 and
# has no clear lane west of that.  Left alone.

open(dst, "w").write("\n".join("".join(r).rstrip() for r in rows))
print("wrote", dst)
