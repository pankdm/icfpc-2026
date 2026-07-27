#!/usr/bin/env python3
"""Cell census of a .man: what fraction of the box is payload vs overhead.

Never prints the grid.  Usage: census.py <f.man> [--rows]
"""
import collections, sys
p = sys.argv[1]
L = [l.rstrip("\n") for l in open(p)]
w = max((len(l.rstrip()) for l in L), default=0)
h = max((i + 1 for i, l in enumerate(L) if l.strip()), default=0)
grid = [(l + " " * w)[:w] for l in L[:h]]
c = collections.Counter(ch for row in grid for ch in row)
tot = w * h
dig = sum(c[d] for d in "0123456789")
bt = c["`"]
blank = c[" "]
wall = c["-"] + c["|"] + c["+"]
pipe = c["<"] + c[">"] + c["^"] + c["v"]
other = tot - dig - bt - blank - wall - pipe
print("box %dx%d = %d" % (w, h, max(w, h) ** 2))
print("  digits   %5d  %5.1f%%" % (dig, 100 * dig / tot))
print("  backtick %5d  %5.1f%%   (=%d slots, %.1f digits/slot)"
      % (bt, 100 * bt / tot, bt // 2, dig / max(1, bt // 2)))
print("  blank    %5d  %5.1f%%" % (blank, 100 * blank / tot))
print("  wall     %5d  %5.1f%%" % (wall, 100 * wall / tot))
print("  pipe     %5d  %5.1f%%" % (pipe, 100 * pipe / tot))
print("  ops      %5d  %5.1f%%" % (other, 100 * other / tot))
print("  cells outside bbox-square: %d" % (max(w, h) ** 2 - tot))
if "--rows" in sys.argv:
    for i, row in enumerate(grid):
        d = sum(1 for ch in row if ch.isdigit())
        b = row.count("`")
        s = row.count(" ")
        print("   r%-3d dig %3d bt %3d blank %3d other %3d" % (i, d, b, s, w - d - b - s))
