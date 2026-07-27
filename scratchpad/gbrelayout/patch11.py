#!/usr/bin/env python3
"""TOP id handler: pull its turnaround east to the R2 write band edge.

After the band swap the handler is `W s(R2) ... r(R4) b s(R4)`.  Only the R2
write is band-locked, to cols 15-20, and `W` merely has to precede it -- so the
turnaround belongs at col 15, not col 12.  (Col 12 was chosen when `W` still sat
at 14 to keep clear of col 13, which carries a foreign path at count 64; with
`W` at 16 that column is only ever a glide, which is safe.)

  12 -> 15:  -3 cells each way x32 students = -192 ticks
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


clr(12, 49, "v"); clr(12, 50, ">")
clr(14, 50, "W"); clr(15, 50, "s")
put(15, 49, "v"); put(15, 50, ">")
put(16, 50, "W"); put(17, 50, "s")

open(dst, "w").write("\n".join("".join(r).rstrip() for r in rows))
print("wrote", dst)
