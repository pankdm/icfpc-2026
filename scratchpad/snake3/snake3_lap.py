#!/usr/bin/env python3
"""Print ONE lap of a chosen walker as a compact op/glide sequence.

Never prints the grid.  Output is a list of segments:
    OP  <glyph> @ (x,y)
    GLIDE n cells (x0,y0)->(x1,y1)
so a long pure-travel stretch is visible next to the ops it connects.

  python3 snake3_lap.py <man> <walker> [case] [cap] [start_tick] [max_segments]
"""
import json
import os
import subprocess
import sys

REPO = "/Users/visenbaev/icfpc26"
LM = os.path.join(REPO, "interp", "target", "release", "lm")

man = sys.argv[1]
wi = int(sys.argv[2])
case = int(sys.argv[3]) if len(sys.argv) > 3 else 4
cap = int(sys.argv[4]) if len(sys.argv) > 4 else 20480
start = int(sys.argv[5]) if len(sys.argv) > 5 else 0
maxseg = int(sys.argv[6]) if len(sys.argv) > 6 else 120

spec = json.load(open(os.path.join(REPO, "tests", "snake.json")))
tc = spec["publicTestData"][case]
rs = tc.get("rounds") or [tc]
inp = " / ".join(" ".join(r.get("in") or []) for r in rs)
exp = " / ".join(" ".join(r.get("out") or []) for r in rs)
p = subprocess.run([LM, man, "--trace", f"--input={inp}", f"--expected={exp}",
                    f"--cap={cap}"], capture_output=True, text=True)

rows = open(man).read().split("\n")
W = max(len(r) for r in rows)
rows = [r.ljust(W) for r in rows]
TURN = set("<>^v")


def g(x, y):
    return rows[y][x] if 0 <= y < len(rows) and 0 <= x < W else " "


seq = []
for line in (p.stdout or "").splitlines():
    parts = line.split("|")
    if len(parts) > wi + 1:
        f = parts[wi + 1].split()
        if len(f) >= 5:
            seq.append((int(f[0]), int(f[1]), int(f[2]), int(f[3]), int(f[4])))

print(f"walker {wi}: {len(seq)} ticks")
i = start
n = 0
while i < len(seq) and n < maxseg:
    x, y, a, b, bp = seq[i]
    ch = g(x, y)
    if ch != " " and ch not in TURN:
        print(f"t{i:6d} OP {ch!r} @({x},{y}) A={a} B={b} BP={bp}")
        i += 1
    else:
        j = i
        while j < len(seq):
            cx, cy, *_ = seq[j]
            c = g(cx, cy)
            if c != " " and c not in TURN:
                break
            j += 1
        x1, y1, *_ = seq[j - 1]
        print(f"t{i:6d} GLIDE {j - i:3d}  ({x},{y})->({x1},{y1})")
        i = j
    n += 1
