#!/usr/bin/env python3
"""trace.py <man> <from> <to> [case] — man0's cell/glyph sequence over a tick window."""
import json, subprocess, sys, os
REPO = "/Users/visenbaev/icfpc26"
os.chdir(REPO)
man, t0, t1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
sub = sys.argv[4] if len(sys.argv) > 4 else "N=16"
d = json.load(open("tests/gradebook.json"))
c = [x for x in d["publicTestData"] if sub in x["name"]][0]
rs = c["rounds"]
inp = " / ".join(" ".join(r.get("in") or []) for r in rs)
exp = " / ".join(" ".join(r.get("out") or []) for r in rs)
p = subprocess.Popen(["interp/target/release/lm", man, str(t1 + 2), "--input=" + inp,
                      "--expected=" + exp, "--cap=3000000"],
                     stdout=subprocess.PIPE, text=True, bufsize=1 << 20)
rows = open(man).read().split("\n")
seq = []
for i, line in enumerate(p.stdout):
    if i < t0:
        continue
    if i > t1:
        break
    o = json.loads(line)
    r = o["runners"][0]
    x, y = r["pos"] if isinstance(r.get("pos"), list) else (r["x"], r["y"])
    ch = rows[y][x] if y < len(rows) and x < len(rows[y]) else " "
    seq.append((i, x, y, ch, r.get("a"), r.get("bp")))
p.stdout.close(); p.kill()
out = []
for (i, x, y, ch, a, b) in seq:
    out.append(f"{i}:({x},{y}){ch if ch!=' ' else '.'}" + (f"[A={a},B={b}]" if ch not in " ><^vV" else ""))
print(" ".join(out))
