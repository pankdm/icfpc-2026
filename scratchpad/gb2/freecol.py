#!/usr/bin/env python3
"""Columns of room0 with no glyph over a given row range (candidate vertical corridors)."""
import sys
man, y0, y1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
rows = open(man).read().split("\n")
w = max(len(r) for r in rows)
free = []
for c in range(1, 60):
    ok = True
    for y in range(y0, y1 + 1):
        if c < len(rows[y]) and rows[y][c] != " ":
            ok = False
            break
    if ok:
        free.append(c)
print(f"free cols over rows {y0}-{y1}: {free}")
