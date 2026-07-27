#!/usr/bin/env python3
"""Per-row and per-column occupancy extents of a .man -- what actually sets the box.

  python3 scratchpad/plot3/shape.py <man>
"""
import sys

man = sys.argv[1]
rows = open(man).read().split("\n")
while rows and not rows[-1].strip():
    rows.pop()
w = max(len(r) for r in rows)
rows = [r.ljust(w) for r in rows]
h = len(rows)
print("grid %dx%d  box %d" % (w, h, max(w, h) ** 2))

print("ROWS (row: lo-hi n)")
for y in range(h):
    xs = [x for x in range(w) if rows[y][x] != " "]
    print("  %2d: %s" % (y, "%2d-%2d n=%d" % (xs[0], xs[-1], len(xs)) if xs else "empty"))

print("COLS (col: lo-hi n)")
for x in range(w):
    ys = [y for y in range(h) if rows[y][x] != " "]
    print("  %2d: %s" % (x, "%2d-%2d n=%d" % (ys[0], ys[-1], len(ys)) if ys else "empty"))
