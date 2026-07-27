#!/usr/bin/env python3
"""Which columns reach the last N rows / last M columns of a .man?"""
import sys
from collections import Counter

rows = open(sys.argv[1]).read().split("\n")
while rows and not rows[-1].strip():
    rows.pop()
h = len(rows)
w = max(len(r) for r in rows)
print(f"{w}x{h}")
for y in range(h - 1, max(-1, h - 12), -1):
    nz = [(x, rows[y][x]) for x in range(len(rows[y])) if rows[y][x] != " "]
    print(f"y={y:4d} n={len(nz):4d} x {nz[0][0] if nz else '-'}..{nz[-1][0] if nz else '-'}"
          f"  {''.join(c for _, c in nz[:60])}")
print()
for x in range(w - 1, max(-1, w - 12), -1):
    nz = [(y, rows[y][x]) for y in range(h) if x < len(rows[y]) and rows[y][x] != " "]
    print(f"x={x:4d} n={len(nz):4d} y {nz[0][0] if nz else '-'}..{nz[-1][0] if nz else '-'}"
          f"  {''.join(c for _, c in nz[:60])}")
