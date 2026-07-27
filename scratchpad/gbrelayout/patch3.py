#!/usr/bin/env python3
"""Fix patch2's regression: B=128 was lost on the accumulator return.

MEASURED: r2's ring is 18 ticks (was 28) but 32 of the 144 iterations moved to
the 66-tick id path, +96 net.  Cause: the found-target exit runs the accumulator,
whose `M` at (19,39) sets B=1, and that path re-enters the ring at (29,36)^
WITHOUT crossing row 36's `7 M 1 {` -- so `-` computed v-1 and every grade
classified as an id.

Fix: rebuild the constant on the accumulator return too, and move the final
`M` onto (29,34), which is on BOTH entry corridors and on neither ring leg.
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


# accumulator return leg: A=1, B=7 -> A=1<<7=128
put(26, 39, "7")
put(27, 39, "M")
put(28, 39, "1")
put(29, 38, "{")          # also on the align loop's A==0 detour: 0<<B = 0, harmless

# both entries funnel through (29,34): park B=128 there instead of on row 36
clr(29, 35, "N")          # (29,35) is shared by the ring's west leg and the entry
put(28, 35, "N")
put(29, 34, "M")
clr(18, 36, "M")          # row 36 now only builds A=128; (29,34) does the M

open(dst, "w").write("\n".join("".join(r).rstrip() for r in rows))
print("wrote", dst)
