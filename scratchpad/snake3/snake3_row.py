#!/usr/bin/env python3
"""Print the op content of chosen rows as (col, glyph) pairs -- never the grid.
Also reports, per cell, how many times the traced walker executed it, which is
the placement oracle: a destination cell is only safe if its walk count equals
the moving op's own iteration count.

  python3 snake3_row.py <man> <row> [row ...] [--walker N] [--case N] [--cap N]
"""
import collections
import json
import os
import subprocess
import sys

REPO = "/Users/visenbaev/icfpc26"
LM = os.path.join(REPO, "interp", "target", "release", "lm")

args = [a for a in sys.argv[1:]]
man = args.pop(0)
opt = {"walker": 3, "case": 4, "cap": 20480}
want = []
i = 0
while i < len(args):
    if args[i].startswith("--"):
        opt[args[i][2:]] = int(args[i + 1])
        i += 2
    else:
        want.append(int(args[i]))
        i += 1

spec = json.load(open(os.path.join(REPO, "tests", "snake.json")))
tc = spec["publicTestData"][opt["case"]]
rs = tc.get("rounds") or [tc]
inp = " / ".join(" ".join(r.get("in") or []) for r in rs)
exp = " / ".join(" ".join(r.get("out") or []) for r in rs)
p = subprocess.run([LM, man, "--trace", f"--input={inp}", f"--expected={exp}",
                    f"--cap={opt['cap']}"], capture_output=True, text=True)

rows = open(man).read().split("\n")
W = max(len(r) for r in rows)
rows = [r.ljust(W) for r in rows]

hits = collections.Counter()
for line in (p.stdout or "").splitlines():
    parts = line.split("|")
    if len(parts) > opt["walker"] + 1:
        f = parts[opt["walker"] + 1].split()
        if len(f) >= 2:
            hits[(int(f[0]), int(f[1]))] += 1

for y in want:
    cells = [(x, rows[y][x], hits[(x, y)]) for x in range(W) if rows[y][x] != " "]
    print(f"row {y}: {len(cells)} non-space cells")
    print("  " + "  ".join(f"{x}{ch!r}x{n}" for x, ch, n in cells))
