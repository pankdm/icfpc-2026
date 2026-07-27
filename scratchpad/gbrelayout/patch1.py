#!/usr/bin/env python3
"""Roster-load loop: shrink the cycle from 72 to 62 ticks.

The loop reads one roster value at the IN band (cols 1-5) and pushes it at the
belt-out band (cols 32-37), so its two long legs are band-forced.  What is NOT
forced is where it turns around: it currently runs east to col 35 and west to
col 1.  Pull the east turn in to col 33 (s is at 32) and the west turn in to
col 4 (r moves to col 5, the east edge of the IN band).

  before: 1>,2r ... 32s ... 35v / 35< ... 16m,15d / 15< ... 1v      72 ticks
  after:  4>,5r ... 32s,33v      / 33< ... 16m,15d / 15< ... 4v      62 ticks

79 iterations on the N=16 K=4 case -> -790 ticks.
"""
import sys

src = sys.argv[1]
dst = sys.argv[2]
rows = [list(r) for r in open(src).read().split("\n")]
w = max(len(r) for r in rows)
for r in rows:
    r.extend(" " * (w - len(r)))


def put(x, y, ch):
    assert rows[y][x] in (" ", ch), "occupied (%d,%d)=%r" % (x, y, rows[y][x])
    rows[y][x] = ch


def clr(x, y, expect):
    assert rows[y][x] == expect, "expected %r at (%d,%d), got %r" % (expect, x, y, rows[y][x])
    rows[y][x] = " "


# east turn 35 -> 33
clr(35, 3, "v"); clr(35, 4, "<")
put(33, 3, "v"); put(33, 4, "<")
# west turn 1 -> 4, r 2 -> 5
clr(1, 2, "v"); clr(1, 3, ">"); clr(2, 3, "r")
put(4, 2, "v"); put(4, 3, ">"); put(5, 3, "r")

open(dst, "w").write("\n".join("".join(r).rstrip() for r in rows))
print("wrote", dst)
