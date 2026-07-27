#!/usr/bin/env python3
"""Summarise an lm --profile dump: controller vs satellite, stalls, hot cells."""
import ast
import re
import sys
from collections import Counter

txt = open(sys.argv[1]).read()
CTRL_MAXY = int(sys.argv[2]) if len(sys.argv) > 2 else 248


def sect(name):
    m = re.search(rf"PROFILE {name}=(\[.*?\])\n(?=PROFILE|\Z)", txt, re.S)
    return ast.literal_eval(m.group(1)) if m else []


cells = sect("cells")
ctrl = [(p, n) for p, n in cells if p[1] <= CTRL_MAXY]
sat = [(p, n) for p, n in cells if p[1] > CTRL_MAXY]
print("controller cell-executions", sum(n for _, n in ctrl),
      "over", len(ctrl), "cells")
print("satellite  cell-executions", sum(n for _, n in sat),
      "over", len(sat), "cells")
m = re.search(r"PROFILE stall_total=(\S+)", txt)
print("stall_total:", m.group(1) if m else "?")
st = sect("stalls")
print("stalls top 20:")
tot = sum(n for _, n in st) if st else 0
print("  stall sum", tot)
for k, n in st[:20]:
    print("   ", k, n)

# controller: split by glyph kind
grid = open(sys.argv[3]).read().split("\n") if len(sys.argv) > 3 else None
if grid:
    kinds = Counter()
    for (x, y), n in ctrl:
        ch = grid[y][x] if y < len(grid) and x < len(grid[y]) else "?"
        kinds[ch] += n
    print("controller by glyph:", kinds.most_common(20))
    print("  glide(' ') share", kinds.get(" ", 0) / max(1, sum(kinds.values())))
    print("  turns(<>^v)", sum(kinds.get(c, 0) for c in "<>^v"))
print("top controller cells:")
for p, n in ctrl[:15]:
    print("   ", p, n)
