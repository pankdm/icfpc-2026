#!/usr/bin/env python3
"""What sets subset-sum's width 95, and how many replicas are there?

The grid is 95x92 -> box is WIDTH-bound, so cutting replicas (which only removes
rows) pays nothing until width < 92.  Find the rightmost ink per row and the
columns only a handful of rows use -- those are the cheap ones to reclaim.

    python3 scratchpad/ss2/width.py [file.man]
"""
import sys
from collections import Counter

MAN = sys.argv[1] if len(sys.argv) > 1 else "scratchpad/ss2/teammate.man"
g = [l.rstrip("\n") for l in open(MAN).read().split("\n")]
while g and not g[-1].strip():
    g.pop()
W = max(len(l) for l in g)
H = len(g)

# column occupancy
colcnt = Counter()
for l in g:
    for x, c in enumerate(l):
        if c != " ":
            colcnt[x] += 1

print("grid %dx%d  box=%d  max(w,h)=%s" % (W, H, max(W, H) ** 2,
                                           "WIDTH" if W > H else "height"))
print("\nrightmost 12 columns (col: rows using it):")
for x in range(W - 1, W - 13, -1):
    rows = [y for y, l in enumerate(g) if x < len(l) and l[x] != " "]
    print("  col %2d: %3d rows   %s" % (x, colcnt[x],
                                        str(rows[:10])[:56]))

print("\nrows reaching the rightmost column (%d):" % (W - 1))
for y, l in enumerate(g):
    if len(l) >= W and l[W - 1] != " ":
        print("  row %2d: ...%s" % (y, l[W - 20:]))

# replica count: rows matching the worker signatures
sigs = ["|^xrs^|", "| vmdvv|", "]^]W<"]
for s in sigs:
    ys = [y for y, l in enumerate(g) if s in l]
    d = Counter(b - a for a, b in zip(ys, ys[1:]))
    print("\n'%s': %d occurrences, rows %d..%d, period %s"
          % (s, len(ys), min(ys), max(ys), d.most_common(2)))
