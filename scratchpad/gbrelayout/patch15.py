#!/usr/bin/env python3
"""AVG's and TOP's rings: fold the sentinel X's turn INTO the west leg.

Both rings test the raw belt value for the sentinel with an X whose common case
(v>0) turns north onto a `<`, then spends two more cells (`v` then `<`) dropping
back to the west leg one row below.  Put the west leg on the row the `<` is
already on and those two cells vanish:

  before   row A:  <  v            row A+1:  X ... - _ N _ X   (leg)
  after    row A:  <  <  -  N _ m X   (leg)     row A+1:  X ... ^

The rare v==0 case (a zero grade) goes straight west one cell and climbs the
`^` onto the same leg, landing on the second `<`.  `m` now runs before the
classify, so ids decrement BP too -- harmless, since every id's handler reloads
BP immediately after.

-2 cells x144 (AVG) and x96 (TOP) = -480 ticks.  (30,34) and (30,47) are shared
with the align corridor and the ring-entry trunk respectively, so they take the
arithmetic op whose A is overwritten by the next `r` and which never touches B.
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


def refold(leg, old, old_minus):
    clr(31, leg, "v")                       # the drop back to the old leg
    put(31, leg, "<")                       # ...becomes the leg's second turn
    clr(31, old, "<"); put(31, old, "^")    # v==0 climbs here
    clr(old_minus, old, "-"); clr(28, old, "N"); clr(27, old, "X")
    put(30, leg, "-"); put(29, leg, "N"); put(28, leg, "m")
    clr(27, leg, "m"); put(27, leg, "X")


refold(34, 35, 30)      # AVG
refold(47, 48, 29)      # TOP

open(dst, "w").write("\n".join("".join(r).rstrip() for r in rows))
print("wrote", dst)
