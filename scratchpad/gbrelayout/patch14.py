#!/usr/bin/env python3
"""Two pure-travel runs found by ranking glide runs rather than loops.

1. The per-op dispatch (row 10 -> row 11) walks 52 cells of pure travel to turn
   around: east from col 11 to col 30, down, then west from col 30 back to col 1.
   That trip existed to reach the op-count write at (28,10) -- which the band
   swap moved to col 10.  The U-turn now belongs at col 11:

     (11,10)v -> (11,11) -> (11,12)< -> west -> (1,12)^ -> (1,11)>   13 cells

   -39 cells x17 ops = -663 ticks.  Rows 10 and 12 are single-path (count 17
   across their whole width), so nothing else walks the cells being orphaned.

2. TOP's id handler turns around at col 15 because its R2 write sat there, but
   `N` and `+` (which rebuild the id from the parked threshold) are band-free
   and R2's write band runs to col 20.  Turn at 17 instead: -4 x32 = -128.
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


# 1. dispatch U-turn at col 11
clr(30, 10, "v"); clr(30, 12, "<")
put(11, 10, "v"); put(11, 12, "<")

# 2. TOP id handler turnaround 15 -> 17
clr(15, 49, "v"); clr(15, 50, ">")
clr(16, 50, "N"); clr(17, 50, "+"); clr(18, 50, "s")
put(17, 49, "v"); put(17, 50, ">")
put(18, 50, "N"); put(19, 50, "+"); put(20, 50, "s")

open(dst, "w").write("\n".join("".join(r).rstrip() for r in rows))
print("wrote", dst)
