#!/usr/bin/env python3
"""Print a rectangular window of a .man with absolute column indices."""
import sys

MAN = sys.argv[1]
y0, y1 = int(sys.argv[2]), int(sys.argv[3])
x0 = int(sys.argv[4]) if len(sys.argv) > 4 else 0
x1 = int(sys.argv[5]) if len(sys.argv) > 5 else 200

g = open(MAN).read().split("\n")
w = max(len(r) for r in g)
x1 = min(x1, w)
print("     " + "".join(str(x // 10 % 10) for x in range(x0, x1)))
print("     " + "".join(str(x % 10) for x in range(x0, x1)))
for y in range(y0, y1 + 1):
    row = g[y].ljust(w)
    print("%4d %s" % (y, row[x0:x1]))
for y in range(y0, y1 + 1):
    row = g[y].ljust(w)
    cells = [(x, row[x]) for x in range(x0, x1) if row[x] not in " -|+"]
    if cells:
        print("%4d %s" % (y, cells))
