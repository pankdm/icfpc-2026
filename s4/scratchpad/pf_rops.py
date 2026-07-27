#!/usr/bin/env python3
"""Rank controller r/s ops by tick cost, tagged with their port band."""
import ast
import json
import re
import sys
from collections import Counter

txt = open(sys.argv[1]).read()
CTRL_MAXY = int(sys.argv[2])
grid = open(sys.argv[3]).read().split("\n")
cfg = json.load(open(sys.argv[4]))
ports = sorted(cfg["ports"].items(), key=lambda kv: kv[1])

m = re.search(r"PROFILE cells=(\[.*?\])\n(?=PROFILE|\Z)", txt, re.S)
cells = ast.literal_eval(m.group(1))
ms = re.search(r"PROFILE stalls=(\[.*?\])\n(?=PROFILE|\Z)", txt, re.S)
stalls = dict(ast.literal_eval(ms.group(1))) if ms else {}


def nearest(x, glyph):
    best = None
    for n, c in ports:
        if cfg["ports"][n] and n[0] != glyph[0]:
            pass
        want = "s" if glyph == "s" else "r"
        if (n[0] == "s" and n not in ("sc", "sp", "sd", "sa", "ss")) or True:
            pass
        cand = ("s" if n in ("sp", "sc", "sd", "sa", "ss", "qs") else "r")
        if cand != want:
            continue
        d = abs(c - x)
        if best is None or d < best[0]:
            best = (d, n)
    return best[1]


by_port = Counter()
rows = []
for (x, y), n in cells:
    if y > CTRL_MAXY:
        continue
    ch = grid[y][x] if y < len(grid) and x < len(grid[y]) else " "
    if ch not in "rs":
        continue
    p = nearest(x, ch)
    by_port[p] += n
    rows.append(((x, y), p, n, stalls.get((x, y), 0)))
print("ticks spent on port ops, by port:")
for p, n in by_port.most_common():
    print(f"  {p:3s} {n:8d}")
print("total", sum(by_port.values()))
print("\ntop 20 individual port ops (pos, port, ticks, stall):")
for r in rows[:20]:
    print("  ", r)
