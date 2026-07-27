#!/usr/bin/env python3
"""Per-column controller tick cost from an lm --profile cells dump."""
import ast
import re
import sys

txt = open(sys.argv[1]).read()
CTRL_MAXY = int(sys.argv[2])
grid = open(sys.argv[3]).read().split("\n")

m = re.search(r"PROFILE cells=(\[.*?\])\n(?=PROFILE|\Z)", txt, re.S)
cells = ast.literal_eval(m.group(1))
W = max(len(r) for r in grid)
blank = [0] * (W + 2)
op = [0] * (W + 2)
for (x, y), n in cells:
    if y > CTRL_MAXY:
        continue
    ch = grid[y][x] if y < len(grid) and x < len(grid[y]) else " "
    if ch == " ":
        blank[x] += n
    else:
        op[x] += n
print("total blank", sum(blank), "op", sum(op))
print(" col   blank      op   cum-blank%")
cum = 0
tot = sum(blank)
for x in range(W):
    if blank[x] or op[x]:
        cum += blank[x]
        print(f"{x:4d} {blank[x]:8d} {op[x]:8d}  {100*cum/tot:5.1f}")
