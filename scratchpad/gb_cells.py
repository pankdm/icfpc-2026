#!/usr/bin/env python3
"""Exact cell listing for a row window: 'x:glyph' for every non-space cell."""
import sys
f = sys.argv[1]
y0, y1 = int(sys.argv[2]), int(sys.argv[3])
lines = open(f).read().split("\n")
for y in range(y0, y1 + 1):
    row = lines[y]
    items = [f"{x}{row[x]}" for x in range(1, min(len(row), 38)) if row[x] != " "]
    print(f"{y:3d}  " + " ".join(items))
