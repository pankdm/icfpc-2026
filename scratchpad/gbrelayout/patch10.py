#!/usr/bin/env python3
"""Two column-packs worth 142 ticks on the heavy case.

1. AVG id handler.  The B=128 rebuild needs five ops (7 M 1 { M) but only the
   first four have to sit on the WESTBOUND row-37 leg -- the closing `M` can go
   on the eastbound row-36 leg instead, which the man walks anyway.  That lets
   the turnaround move from col 21 to col 22: -2 ticks x48 students.

2. AVG accumulator return.  The same rebuild plus the BP guard occupied six
   cells (23-28) on row 39.  `b` only has to leave BP above K, and A is 7 after
   the closing `W`, so `b` can ride the vertical climb at (29,38) -- a cell this
   build just freed.  Row 39 starts one column later: -1 tick x46.

(29,38) is also on ALIGN's A==0 detour, which is safe: align never reads BP, and
the first belt value after align is always an id, whose handler sets BP.
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


# 1. move the closing M of the B=128 rebuild onto the eastbound leg
clr(22, 37, "M"); clr(21, 37, "^"); clr(21, 36, ">")
put(22, 37, "^"); put(22, 36, ">"); put(23, 36, "M")

# 2. pack the accumulator return and hang the BP guard on the climb
clr(23, 39, "7"); clr(24, 39, "M"); clr(25, 39, "1")
clr(26, 39, "{"); clr(27, 39, "b"); clr(28, 39, "W")
put(24, 39, "7"); put(25, 39, "M"); put(26, 39, "1")
put(27, 39, "{"); put(28, 39, "W")
put(29, 38, "b")

open(dst, "w").write("\n".join("".join(r).rstrip() for r in rows))
print("wrote", dst)
