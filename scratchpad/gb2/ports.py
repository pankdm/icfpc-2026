#!/usr/bin/env python3
"""List every r/s/q/R/U op in room0 with the pipe it binds and its execution count."""
import sys, os, re, ast, subprocess
sys.path.insert(0, "/Users/visenbaev/icfpc26/tools")
sys.path.insert(0, "/Users/visenbaev/icfpc26/scratchpad")
import walkfold as W

man = sys.argv[1]
rows = W.load_rows(man)
g = W.Grid(rows)
tab, pure, inc, out = W.bands(g, 0)
(x0, y0), (x1, y1) = g.rooms[0]["min"], g.rooms[0]["max"]

counts = {}
if len(sys.argv) > 2:
    from gb_bench import build, KINDS, LM
    kind = sys.argv[2]
    N = int(sys.argv[3]) if len(sys.argv) > 3 else 16
    K = int(sys.argv[4]) if len(sys.argv) > 4 else 4
    inp, exp = build(N, K, KINDS[kind], 10, 8)
    p = subprocess.run([LM, "--profile", man, f"--input={inp}", f"--expected={exp}",
                        "--cap=5000000"], capture_output=True, text=True)
    m = re.search(r"PROFILE cells=(\[.*?\])\nPROFILE stall", p.stderr, re.S)
    counts = {tuple(c): n for c, n in ast.literal_eval(m.group(1))}

print("in bands :", {p: (min(x for x in tab if tab[x]['in'] == p),
                         max(x for x in tab if tab[x]['in'] == p))
                     for p in {tab[x]['in'] for x in tab}})
print("out bands:", {p: (min(x for x in tab if tab[x]['out'] == p),
                         max(x for x in tab if tab[x]['out'] == p))
                     for p in {tab[x]['out'] for x in tab}})
for y in range(y0 + 1, y1):
    for x in range(x0 + 1, x1):
        ch = g.at(x, y)
        if ch in "rsqRUS":
            kind = "out" if ch in "sS" else "in"
            print(f"  ({x:2d},{y:2d}) {ch}  pipe{tab[x][kind]}  n={counts.get((x, y), 0)}")
