#!/usr/bin/env python3
"""For every R1 and R4 pipe op, can it slide into the other register's band for free?

An op can slide horizontally at zero tick cost only if the man's walk already
covers the destination column ON THAT ROW.  Uses the profiler's per-cell counts
as the walk oracle: a cell with count 0 is not walked, so putting an op there
means lengthening the walk.

  python3 scratchpad/gbrelayout/bandmove.py <man>
"""
import ast, json, os, subprocess, sys

REPO = "/Users/visenbaev/icfpc26"
LM = os.path.join(REPO, "interp", "target", "release", "lm")
man = sys.argv[1]

spec = json.load(open(os.path.join(REPO, "tests", "gradebook.json")))
tc = spec["publicTestData"][-1]
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

# in-bands: IN 1-5, R1 6-11, R2 12-17, R3 18-23, R4 24-28, belt 29-37
# out-bands: OUT 1-8, R1 9-14, R2 15-20, R3 21-26, R4 27-31, belt 32-37
GROUPS = [("R1 read", "rRUq", range(6, 12), range(24, 29)),
          ("R1 write", "sS", range(9, 15), range(27, 32)),
          ("R4 read", "rRUq", range(24, 29), range(6, 12)),
          ("R4 write", "sS", range(27, 32), range(9, 15))]

for name, glyphs, band, dest in GROUPS:
    print("== %s (band %d-%d -> %d-%d)" % (name, band[0], band[-1], dest[0], dest[-1]))
    for y in range(1, 57):
        for x in band:
            if rows[y][x] in glyphs:
                free = [d for d in dest if rows[y][d] == " " and cells.get((d, y), 0) > 0]
                same = [d for d in free if cells.get((d, y), 0) == cells.get((x, y), 0)]
                print("   (%2d,%2d)%s cnt=%-6d walked+empty in dest: %s   same-count: %s"
                      % (x, y, rows[y][x], cells.get((x, y), 0), free or "NONE", same or "NONE"))
