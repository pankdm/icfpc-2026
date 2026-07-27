#!/usr/bin/env python3
"""GET's and SET's id-scan rings: 12 ticks -> 8.

Both rings compare the belt value to the target id with `-` (A = v - id).  The
answer is signed, so "no match" arrives as A>0 OR A<0 and the ring needs TWO
return paths -- (31,15)X -> N -> (31,14)> for one sign and
(31,15)X -> S -> (31,16)> -> (32,16)^ for the other.  That second path is what
makes the ring 12 cells wide-and-tall instead of a flat 4x2.

`~` (XOR) answers the same question unsigned: v XOR id is 0 iff equal and
POSITIVE otherwise (both operands are non-negative -- the sentinel is never
reached, since the target id is guaranteed present after ALIGN, which is the
same assumption the `-` version already relies on to terminate).  One sign
means one turn direction, so the X can sit on the ring's north-turning corner
and the ring closes as a bare 4x2:

    >rsv / <~_X      8 cells, B (the target id) is already parked for `-`
"""
import sys

src, dst = sys.argv[1], sys.argv[2]
rows = [list(r) for r in open(src).read().split("\n")]
w = max(len(r) for r in rows)
for r in rows:
    r.extend(" " * (w - len(r)))


def swap(x, y, was, now):
    assert rows[y][x] == was, "expected %r at (%d,%d), got %r" % (was, x, y, rows[y][x])
    rows[y][x] = now


# GET ring, rows 14-16
swap(34, 15, "-", "~")
swap(32, 15, " ", "X")    # north-turning corner: A>0 -> N -> (32,14)'>' -> r
swap(31, 15, "X", " ")    # found (A==0) now falls straight through here
# The sentinel IS reached (lazyalign leaves the belt at an arbitrary rotation,
# so the scan wraps).  v XOR id is negative only for it, so route that one case
# back to the ring's entry turn instead of into the X again.
swap(31, 16, ">", "^")
swap(32, 16, "^", "<")

# SET ring, rows 23-25
swap(33, 24, "-", "~")
swap(32, 24, " ", "X")
swap(31, 24, "X", " ")
swap(31, 25, ">", "^")
swap(32, 25, "^", "<")

open(dst, "w").write("\n".join("".join(r).rstrip() for r in rows))
print("wrote", dst)
