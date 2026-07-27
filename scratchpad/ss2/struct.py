#!/usr/bin/env python3
"""Reverse-engineer the teammate's subset-sum grid: dimensions, rooms, replicas.

Score is max(w,h)^2 x avgTicks, and this grid is far taller than wide, so the
replica count is the lever: fewer workers -> fewer rows -> smaller box, but more
sequential work per worker -> more ticks.  First establish the exact geometry and
the size of one replica so the trade can be modelled instead of guessed.

    python3 scratchpad/ss2/struct.py [file.man]
"""
import sys
from collections import Counter

MAN = sys.argv[1] if len(sys.argv) > 1 else "scratchpad/ss2/teammate.man"
g = open(MAN).read().split("\n")
while g and not g[-1].strip():
    g.pop()

w = max(len(l) for l in g)
h = len(g)
ink = sum(1 for l in g for c in l if c != " ")
print("grid %dx%d  box=%d  ink=%d (%.0f%%)" % (w, h, max(w, h) ** 2, ink,
                                               100.0 * ink / (w * h)))

# room corners: '+' cells
corners = [(x, y) for y, l in enumerate(g) for x, c in enumerate(l) if c == "+"]
print("corner cells: %d" % len(corners))

# repeated row-signatures = the replica bands
sig = Counter(l.rstrip() for l in g if l.strip())
print("\nmost repeated row signatures:")
for s, n in sig.most_common(8):
    if n > 1:
        print("  x%-3d  %s" % (n, s[:74]))

# find the vertical period: rows whose signature repeats a lot
rep = [s for s, n in sig.items() if n >= 5]
rows_in_band = [y for y, l in enumerate(g) if l.rstrip() in rep]
if rows_in_band:
    lo, hi = min(rows_in_band), max(rows_in_band)
    print("\nreplica band rows %d..%d  (%d rows, %d of them repeated)"
          % (lo, hi, hi - lo + 1, len(rows_in_band)))
    # period = spacing between successive occurrences of the commonest row
    top = sig.most_common(1)[0][0]
    ys = [y for y, l in enumerate(g) if l.rstrip() == top]
    if len(ys) > 1:
        d = [b - a for a, b in zip(ys, ys[1:])]
        print("period between '%s' rows: %s" % (top[:30], Counter(d).most_common(3)))
        print("replica count (that row): %d" % len(ys))
