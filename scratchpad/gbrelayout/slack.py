#!/usr/bin/env python3
"""Find rows whose walk reaches further west than any band-locked op requires.

`r`/`s`/`q` are pinned to a pipe's column band; every other glyph is free to
slide.  So on a row whose leftmost glyph sits west of its leftmost pipe op, the
extra columns are only travel -- unless a non-pipe op there is genuinely needed
in that order.  Prints the gap and the glyphs occupying it, biggest tick cost
first (gap x the row's walk count).

  python3 scratchpad/gbrelayout/slack.py <man>
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

out = []
for y in range(1, 57):
    gl = [x for x in range(1, 38) if rows[y][x] != " "]
    pipe = [x for x in gl if rows[y][x] in "rRUqsS"]
    if not gl or not pipe:
        continue
    lo, plo = gl[0], pipe[0]
    if plo - lo < 2:
        continue
    n = max(cells.get((x, y), 0) for x in range(lo, plo + 1))
    out.append((n * (plo - lo), y, lo, plo, n,
                "".join(rows[y][x] if rows[y][x] != " " else "." for x in range(lo, plo + 1))))
out.sort(reverse=True)
for cost, y, lo, plo, n, s in out[:14]:
    print("row %2d  cols %2d-%2d  walk x%-5d  potential %5d  |%s|" % (y, lo, plo, n, cost, s))
