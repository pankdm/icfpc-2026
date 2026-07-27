#!/usr/bin/env python3
"""Pull AVG's and TOP's id-handler turnarounds east, as far as their bands allow.

Both handlers only reload BP with the subject index from R1, so nothing in them
needs to be west of the R1 bands (read 6-11, write 9-14) -- yet AVG turns around
at col 5 and TOP at col 7.

The first attempt at this went further east and broke: MEASURED per-cell counts
say col 12 on rows 36/37 is a vertical corridor (96 passes vs the handler's 48),
col 13 there carries 50, col 16 carries 55, and col 13 on rows 49/50 carries 64.
Placing `b`/`s` on any of those fires them on a foreign path.  Cols 8-11 (rows
36/37) and 9-12,14 (rows 49/50) are clean at exactly the handler's own count.

  AVG  ^/> at 5, r@7 b@9 s@10   ->  ^/> at 8, r@9 b@10 s@11    -6 ticks x48
  TOP  v/> at 7, r@8 b@9 s@10 W@12 -> v/> at 9, r@10 b@11 s@12 W@14  -4 x32
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


# AVG id handler: turnaround 5 -> 8
clr(5, 37, "^"); clr(5, 36, ">"); clr(6, 36, ">")
clr(7, 36, "r"); clr(9, 36, "b"); clr(10, 36, "s")
put(8, 37, "^"); put(8, 36, ">")
put(9, 36, "r"); put(10, 36, "b"); put(11, 36, "s")

# TOP id handler: turnaround 7 -> 9
clr(7, 49, "v"); clr(7, 50, ">")
clr(8, 50, "r"); clr(9, 50, "b"); clr(10, 50, "s"); clr(12, 50, "W")
put(9, 49, "v"); put(9, 50, ">")
put(10, 50, "r"); put(11, 50, "b"); put(12, 50, "s"); put(14, 50, "W")

open(dst, "w").write("\n".join("".join(r).rstrip() for r in rows))
print("wrote", dst)
