#!/usr/bin/env python3
"""AVG's and TOP's per-student id handlers: pull their turnarounds east.

Both handlers exist only to reload BP with the subject index from R1, so their
west extent is set by the R1 bands (read 6-11, write 9-14) -- but both currently
turn around at col 5/7, several columns west of anything they need.

  AVG  row 37/36:  (5,37)^ (5,36)> (6,36)> (7,36)r (9,36)b (10,36)s
        ->         (10,37)^ (10,36)> (11,36)r (12,36)b (13,36)s
        22 cells each way -> 17.  x48 students = -480 ticks.

  TOP  row 49/50:  (7,49)v (7,50)> (8,50)r (9,50)b (10,50)s (12,50)W
        ->         (10,49)v (10,50)> (11,50)r (12,50)b (13,50)s (14,50)W
        x~32 students = -192 ticks.

The `7 M 1 {` that parks B=128 for AVG keeps its columns (14,15,16,17); the
stray `1` at (16,36) is deliberately left where it is because the northbound
col-16 corridor from TOP executes it.
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


# --- AVG id handler --------------------------------------------------------
clr(5, 37, "^"); clr(5, 36, ">"); clr(6, 36, ">")
clr(7, 36, "r"); clr(9, 36, "b"); clr(10, 36, "s")
put(10, 37, "^"); put(10, 36, ">")
put(11, 36, "r"); put(12, 36, "b"); put(13, 36, "s")


open(dst, "w").write("\n".join("".join(r).rstrip() for r in rows))
print("wrote", dst)
