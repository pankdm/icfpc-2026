#!/usr/bin/env python3
"""TOP's "not a new max" return: a ~95-cell detour replaced by ~14 cells.

TRACED: after the max compare at (22,52), the not-a-new-max branch walked north
up col 22, east to col 28, north to row 42, west to col 16, north to row 36,
west to col 3, south to row 50 and east along row 51 -- about 95 cells -- to
reach `W`, the R3 write-back of the old max, and the BP guard.  The only op on
that whole path is a `1` at (16,36) that merely clobbers a dead A.

`W` and the guard are band-free and R3's write band is 21-26, so all four ops
fit immediately above the branch:

    (22,51)>  (23,51)W  (24,51)s  (25,51)9  (26,51)b  ...  (30,51)^

`W` now brings A_old rather than 1 into B, which is dead either way -- TOP's
ring sets B with its own `M` before anything reads it.

7 traversals x ~81 cells = -665 ticks on the heavy case.
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


clr(2, 51, "W"); clr(21, 51, "s"); clr(24, 51, "9"); clr(25, 51, "b")
put(22, 51, ">")
put(23, 51, "W"); put(24, 51, "s"); put(25, 51, "9"); put(26, 51, "b")

open(dst, "w").write("\n".join("".join(r).rstrip() for r in rows))
print("wrote", dst)
