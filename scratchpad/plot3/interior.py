#!/usr/bin/env python3
"""Per-row interior extents of one room, and which interior COLUMNS are empty.

An empty interior column is a free width cut (the walls just close up), which is
the cheapest box move there is.

  python3 scratchpad/plot3/interior.py <man> <x0> <y0> <x1> <y1>
"""
import sys

man = sys.argv[1]
x0, y0, x1, y1 = map(int, sys.argv[2:6])
rows = open(man).read().split("\n")
w = max(len(r) for r in rows)
rows = [r.ljust(w) for r in rows]

print("room [%d,%d]..[%d,%d]  interior %dx%d" % (x0, y0, x1, y1, x1 - x0 - 1, y1 - y0 - 1))
for y in range(y0 + 1, y1):
    xs = [x for x in range(x0 + 1, x1) if rows[y][x] != " "]
    print("  row %2d: %s" % (y, "%2d-%2d n=%d" % (xs[0], xs[-1], len(xs)) if xs else "EMPTY"))

empty = [x for x in range(x0 + 1, x1)
         if all(rows[y][x] == " " for y in range(y0 + 1, y1))]
print("empty interior cols:", empty)
emptyr = [y for y in range(y0 + 1, y1)
          if all(rows[y][x] == " " for x in range(x0 + 1, x1))]
print("empty interior rows:", emptyr)
