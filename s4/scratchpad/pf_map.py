#!/usr/bin/env python3
"""Coarse occupancy map of a .man: per-row and per-column extents."""
import sys

path = sys.argv[1]
rows = open(path).read().split("\n")
while rows and not rows[-1].strip():
    rows.pop()
w = max(len(r) for r in rows)
h = len(rows)
print(f"{w}x{h} box {max(w,h)**2:,}")

# column occupancy
colcnt = [0] * w
rowcnt = [0] * h
for y, r in enumerate(rows):
    for x, c in enumerate(r):
        if c != " ":
            colcnt[x] += 1
            rowcnt[y] += 1
print("\nrows (y: count, first..last x):")
for y in range(h):
    r = rows[y]
    nz = [x for x, c in enumerate(r) if c != " "]
    if not nz:
        print(f"  {y}: EMPTY")
print("\nempty cols:", [x for x in range(w) if colcnt[x] == 0])
print("\nper-16-row band densities:")
for y0 in range(0, h, 16):
    band = rowcnt[y0:y0 + 16]
    print(f"  y {y0:3d}-{min(y0+15,h-1):3d}  cells {sum(band):6d}")
print("\nper-16-col band densities:")
for x0 in range(0, w, 16):
    band = colcnt[x0:x0 + 16]
    print(f"  x {x0:3d}-{min(x0+15,w-1):3d}  cells {sum(band):6d}")
