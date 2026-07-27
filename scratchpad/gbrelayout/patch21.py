#!/usr/bin/env python3
"""TOP's max-update: descend straight into the chain instead of going round row 53.

The chain is pinned only by R2's read band (12-17) and R3's (18-23); its nine ops
plus the 7-cell `16384` literal fit from col 7 to col 22 with X still at 22.  So
the man can walk west along row 45 to col 6 and drop straight onto row 52 --
instead of stopping at col 13, descending to row 53, running west to col 3,
climbing back to row 52 and running east again.

  before  row45 west to 13, col13 down to 53, row53 west to 3, up, row52 east
  after   row45 west to  6, col 6 down to 52, row52 east

Col 6 rows 45-51 are blank with walk count 0 -- no foreign path at all.
~14 cells x32 = -448 ticks.
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


clr(13, 45, "v"); put(6, 45, "v")

for x, ch in ((3, ">"), (5, "`"), (6, "1"), (7, "6"), (8, "3"), (9, "8"), (10, "4"),
              (11, "`"), (12, "*"), (14, "M"), (15, "r"), (16, "N"), (17, "+"),
              (18, "M"), (19, "r")):
    clr(x, 52, ch)
for x, ch in ((6, ">"), (7, "`"), (8, "1"), (9, "6"), (10, "3"), (11, "8"),
              (12, "4"), (13, "`"), (14, "*"), (15, "M"), (16, "r"), (17, "N"),
              (18, "+"), (19, "M"), (20, "r")):
    put(x, 52, ch)

# guard: a second backtick in the same column would open a VERTICAL literal,
# which the Rust engine accepts and the wasm oracle rejects.
cols = {}
for y, row in enumerate(rows):
    for x, ch in enumerate(row):
        if ch == "`":
            cols.setdefault(x, []).append(y)
dupes = {x: ys for x, ys in cols.items() if len(ys) > 1}
assert not dupes, "vertical literal risk: %r" % dupes

open(dst, "w").write("\n".join("".join(r).rstrip() for r in rows))
print("wrote", dst, "backtick cols", sorted(cols))
