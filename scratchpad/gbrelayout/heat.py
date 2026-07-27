#!/usr/bin/env python3
"""Overlay the Rust profiler's per-cell tick counts on the grid.

  python3 scratchpad/gbrelayout/heat.py <man> [case-index]

Prints, per row, the glyphs plus a bucketed heat character, then the per-row
tick totals (which rows own the time) and the per-column totals.
"""
import ast, json, os, subprocess, sys

REPO = "/Users/visenbaev/icfpc26"
LM = os.path.join(REPO, "interp", "target", "release", "lm")

man = sys.argv[1]
idx = int(sys.argv[2]) if len(sys.argv) > 2 else -1

spec = json.load(open(os.path.join(REPO, "tests", "gradebook.json")))
tc = spec["publicTestData"][idx]
rs = tc.get("rounds") or [tc]
inp = " / ".join(" ".join(r.get("in") or []) for r in rs)
exp = " / ".join(" ".join(r.get("out") or []) for r in rs)
p = subprocess.run([LM, "--profile", man, f"--input={inp}", f"--expected={exp}", "--cap=5000000"],
                   capture_output=True, text=True)
cells = {}
for line in ((p.stdout or "") + "\n" + (p.stderr or "")).splitlines():
    if line.startswith("PROFILE cells="):
        for (x, y), n in ast.literal_eval(line[len("PROFILE cells="):]):
            cells[(x, y)] = n

rows = open(man).read().split("\n")
w = max(len(r) for r in rows)
rows = [r.ljust(w) for r in rows]

BUCK = " .:-=+*#%@"


def hc(n):
    if n <= 0:
        return " "
    import math
    b = min(len(BUCK) - 1, 1 + int(math.log10(n) * 2.2))
    return BUCK[b]


rowtot = []
for y, r in enumerate(rows):
    t = sum(cells.get((x, y), 0) for x in range(w))
    rowtot.append(t)
    heat = "".join(hc(cells.get((x, y), 0)) for x in range(w))
    print("%02d %6d |%s| %s" % (y, t, r, heat))

coltot = [sum(cells.get((x, y), 0) for y in range(len(rows))) for x in range(w)]
print("total", sum(rowtot))
print("rows by cost:", sorted(range(len(rowtot)), key=lambda y: -rowtot[y])[:15])
print("cols:", " ".join("%d:%d" % (x, c) for x, c in enumerate(coltot) if c))
