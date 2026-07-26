#!/usr/bin/env python3
"""Per-row execution heatmap of room0 (the critical man) for a chosen op workload.

usage: gb_heat.py <kind> [file.man] [N] [K]      kind in GET SET AVG TOP NONE
"""
import ast, re, subprocess, sys

sys.path.insert(0, "/Users/visenbaev/icfpc26/scratchpad")
from gb_bench import build, KINDS, LM

kind = sys.argv[1] if len(sys.argv) > 1 else "AVG"
MAN = sys.argv[2] if len(sys.argv) > 2 else \
    "/Users/visenbaev/icfpc26/solutions/gradebook/champion-f26bbd24.man"
N = int(sys.argv[3]) if len(sys.argv) > 3 else 16
K = int(sys.argv[4]) if len(sys.argv) > 4 else 4
ROUNDS, PER = (1, 1) if kind == "NONE" else (10, 8)
mk = KINDS["GET" if kind == "NONE" else kind]

inp, exp = build(N, K, mk, ROUNDS, PER)
p = subprocess.run([LM, "--profile", MAN, f"--input={inp}", f"--expected={exp}",
                    "--cap=5000000"], capture_output=True, text=True)
print(p.stdout.strip())
m = re.search(r"PROFILE cells=(\[.*?\])\nPROFILE stall", p.stderr, re.S)
cells = ast.literal_eval(m.group(1))
lines = open(MAN).read().split("\n")
rows, cellmap = {}, {}
for (x, y), c in cells:
    if 0 < y < 75:                      # room0 interior only
        rows[y] = rows.get(y, 0) + c
        cellmap[(x, y)] = c
tot = sum(rows.values())
print(f"room0 executions = {tot}")
for y, c in sorted(rows.items(), key=lambda kv: -kv[1])[:20]:
    print(f"row {y:3d} {c:8d} {100*c/tot:5.1f}%  |{lines[y][1:38]}|")
print("--- hottest cells ---")
for (x, y), c in sorted(cellmap.items(), key=lambda kv: -kv[1])[:20]:
    print(f"  ({x:2d},{y:2d}) {c:8d}  {lines[y][x]!r}")
