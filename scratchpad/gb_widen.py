#!/usr/bin/env python3
"""Widen gradebook room0's east wall so walkfold `fuse` has columns to spend.

usage: gb_widen.py <in.man> <out.man> <newwall_col>
room0 = [0,0]..[38,75].  Right wall col 38 -> newwall.  Interior filled with spaces.
"""
import sys

src, dst, newcol = sys.argv[1], sys.argv[2], int(sys.argv[3])
lines = open(src).read().split("\n")
W = max(len(l) for l in lines)
lines = [l.ljust(W) for l in lines]

OLD = 38
TOP, BOT = 0, 75

# sanity: nothing lives east of OLD on rows TOP..BOT
for y in range(TOP, BOT + 1):
    tail = lines[y][OLD + 1:]
    if tail.strip():
        sys.exit(f"row {y} has content east of wall: {tail!r}")

for y in range(TOP, BOT + 1):
    row = list(lines[y].ljust(max(W, newcol + 1)))
    ch = row[OLD]
    row[OLD] = "-" if ch == "+" else " "
    for x in range(OLD + 1, newcol):
        row[x] = "-" if ch == "+" else " "
    row[newcol] = ch
    lines[y] = "".join(row)

W2 = max(len(l) for l in lines)
open(dst, "w").write("\n".join(l.ljust(W2).rstrip() for l in lines) + "\n")
print(f"wrote {dst}: wall {OLD} -> {newcol}")
