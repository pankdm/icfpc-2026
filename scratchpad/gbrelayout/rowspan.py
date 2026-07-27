#!/usr/bin/env python3
"""Per-row glyph span inside room0 + a greedy interval-graph pairing bound.

  python3 scratchpad/gbrelayout/rowspan.py <man>
"""
import sys

man = sys.argv[1]
rows = open(man).read().split("\n")
w = max(len(r) for r in rows)
rows = [r.ljust(w) for r in rows]

X0, X1, Y0, Y1 = 1, 37, 1, 56   # room0 interior
spans = []
for y in range(Y0, Y1 + 1):
    xs = [x for x in range(X0, X1 + 1) if rows[y][x] != " "]
    if xs:
        spans.append((y, min(xs), max(xs), len(xs)))
    else:
        spans.append((y, None, None, 0))

for y, a, b, n in spans:
    print("%02d %s  n=%2d  span=%s" % (y, ("%2d-%2d" % (a, b)) if a is not None else "  -  ", n,
                                       ("#" * ((b - a + 1)) ).rjust(b + 1) if a is not None else ""))

# greedy pack: sort by left edge, place each row's span into the first "row bin"
# whose current occupancy doesn't overlap (with a 1-col gap).
bins = []
for y, a, b, n in sorted([s for s in spans if s[1] is not None], key=lambda s: s[1]):
    for bin_ in bins:
        if all(b + 1 < ba or a - 1 > bb for (_, ba, bb) in bin_):
            bin_.append((y, a, b))
            break
    else:
        bins.append([(y, a, b)])
print("rows with glyphs:", sum(1 for s in spans if s[1] is not None))
print("greedy interval-packed rows:", len(bins))
