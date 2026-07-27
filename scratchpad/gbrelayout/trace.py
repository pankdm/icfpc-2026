#!/usr/bin/env python3
"""Trace man0's cell sequence for a gradebook case.

  python3 scratchpad/gbrelayout/trace.py <man> <steps> [case-index] [--from N] [--to N]
"""
import json, os, subprocess, sys

REPO = "/Users/visenbaev/icfpc26"
LM = os.path.join(REPO, "interp", "target", "release", "lm")

man = sys.argv[1]
steps = int(sys.argv[2])
idx = int(sys.argv[3]) if len(sys.argv) > 3 and not sys.argv[3].startswith("-") else -1
lo = hi = None
if "--from" in sys.argv:
    lo = int(sys.argv[sys.argv.index("--from") + 1])
if "--to" in sys.argv:
    hi = int(sys.argv[sys.argv.index("--to") + 1])

spec = json.load(open(os.path.join(REPO, "tests", "gradebook.json")))
tc = spec["publicTestData"][idx]
rs = tc.get("rounds") or [tc]
inp = " / ".join(" ".join(r.get("in") or []) for r in rs)
exp = " / ".join(" ".join(r.get("out") or []) for r in rs)

rows = open(man).read().split("\n")
w = max(len(r) for r in rows)
rows = [r.ljust(w) for r in rows]

p = subprocess.run([LM, man, str(steps), f"--input={inp}", f"--expected={exp}", "--cap=5000000"],
                   capture_output=True, text=True)
seq = []
for line in (p.stdout or "").splitlines():
    line = line.strip()
    if not line.startswith("{"):
        continue
    d = json.loads(line)
    r0 = (d.get("runners") or [None])[0]
    if not r0:
        continue
    x, y = r0["pos"]
    seq.append((d["step"], x, y, r0.get("a"), r0.get("b")))

out = []
i = 0
while i < len(seq):
    t, x, y, a, b = seq[i]
    j = i
    while j + 1 < len(seq) and seq[j + 1][1] == x and seq[j + 1][2] == y:
        j += 1
    n = j - i + 1
    g = rows[y][x]
    if (lo is None or t >= lo) and (hi is None or t <= hi):
        out.append("%d:%d,%d%s%s" % (t, x, y, g, ("x%d" % n) if n > 1 else ""))
    i = j + 1
print(" ".join(out))
