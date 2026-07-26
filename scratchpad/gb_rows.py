#!/usr/bin/env python3
"""Per-row census of gradebook room0: ops vs pure-routing glyphs."""
import sys

TURN = set("><^vV")
f = sys.argv[1] if len(sys.argv) > 1 else "solutions/gradebook/champion-f26bbd24.man"
lines = open(f).read().split("\n")
nops = nturn = 0
for y in range(1, 75):
    row = lines[y][1:38]
    ops = [c for c in row if c != " " and c not in TURN]
    turns = [c for c in row if c in TURN]
    nops += len(ops)
    nturn += len(turns)
    print(f"{y:3d} ops={len(ops):2d} turns={len(turns):2d}  |{row}|")
print(f"total ops={nops} turns={nturn}")
