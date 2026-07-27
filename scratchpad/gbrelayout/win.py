#!/usr/bin/env python3
"""Print a window of a .man with absolute row/col rulers.

  python3 scratchpad/gbrelayout/win.py <man> <y0> <y1> [x0] [x1]
"""
import sys

man, y0, y1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
x0 = int(sys.argv[4]) if len(sys.argv) > 4 else 0
x1 = int(sys.argv[5]) if len(sys.argv) > 5 else 46

rows = open(man).read().split("\n")
w = max(len(r) for r in rows)
rows = [r.ljust(w) for r in rows]

print("    " + "".join(str(x // 10 % 10) for x in range(x0, x1 + 1)))
print("    " + "".join(str(x % 10) for x in range(x0, x1 + 1)))
for y in range(y0, y1 + 1):
    print("%3d %s" % (y, rows[y][x0:x1 + 1]))
