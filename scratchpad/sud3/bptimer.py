#!/usr/bin/env python3
"""Compact backpack-counter timer.

The walking timer buys lap length with PATH: a 2-row ring plus a gap excursion
spends ~70 cells spread across the full room width to make a 70-tick lap, which
pins two whole rows of the gadget room.  A backpack counter buys the same lap
with TIME -- a 4-cell inner ring that decrements BP and branches on it -- so the
lap is essentially independent of area:

        lap = 6*N + C                  block = 5 wide x 9 tall

     > m d 1 v        `m` decrements BP; `d` turns CW while BP > 0, so the man
     ^   <   s        cycles > m d < . ^, six ticks per decrement.

The `>` must be INSIDE the ring, immediately before `m`: the return leg arrives
travelling north and `m` sets no direction, so without it the man walks straight
out of the top of the ring into the wall.  It doubles as the birth entry, since
the man is dropped down that same column.
             `        When BP reaches 0 `d` lets him go STRAIGHT, out along the
             0        top row to `1` `s` (emit the all-clear) and then down a
             1        vertical literal that reloads N into A.
             3
             `        `b` writes it back to BP and the bottom row plus the left
             b        column return him into `m`.
       ^ - - <

Tall-and-narrow is the point: 5 columns fits a gap BETWEEN two strips, so the
timer no longer needs its own rows under them.

Registers are safe: the timer is forked from the same `1 N M` init as the
strips, but nothing reads his A or BP, and every strip writes its own BP with
`b` before testing it, so a nonzero BP never leaks.

The FIRST lap is short -- BP starts at 0, so `m` makes it -1, `d` falls straight
through and the timer emits at once, then loads N.  Harmless, because round 1
cannot contain a duplicate, but it does mean the lap must be BISECTED against
the box+lane2 adversaries, never derived.
"""
WIDTH, HEIGHT = 5, 9          # including the entry column at x-1

def place(p, x, y, n):
    """Block occupies (x-1..x+3, y..y+8).  The man is dropped down column x-1
    and turned east into `m` at (x,y)."""
    assert 0 <= n <= 999, n
    p.put(x - 1, y, ">")                       # ring cell AND birth entry
    p.put(x, y, "m")                           # inner ring: 6 ticks / decrement
    p.put(x + 1, y, "d")
    p.put(x + 1, y + 1, "<")
    p.put(x - 1, y + 1, "^")
    p.put(x + 2, y, "1")                       # BP exhausted -> straight through
    p.put(x + 3, y, "v")
    p.put(x + 3, y + 1, "s")
    p.put(x + 3, y + 2, "`")                   # vertical literal, read downward
    for i, ch in enumerate(f"{n:03d}"):
        p.put(x + 3, y + 3 + i, ch)
    p.put(x + 3, y + 6, "`")
    p.put(x + 3, y + 7, "b")                   # BP = N
    p.put(x + 3, y + 8, "<")
    p.put(x - 1, y + 8, "^")                   # return leg climbs the RING column
    return 6 * n + 18

def lap(n):
    return 6 * n + 18
