#!/usr/bin/env python3
"""Where walker 3's glide ticks go: horizontal vs vertical, and the row-to-row
transition matrix weighted by cost.

A boustrophedon-emitted controller pays travel proportional to |row_i - row_j|
for every jump between blocks, so the row ORDER (emission order) is a lever the
column knobs cannot reach.  This prints the total vertical cost and the pairs
that dominate it, which is the payoff bound for reordering.

  python3 snake3_flow.py <man> [walker] [case] [cap]
"""
import collections
import json
import os
import subprocess
import sys

REPO = "/Users/visenbaev/icfpc26"
LM = os.path.join(REPO, "interp", "target", "release", "lm")

man = sys.argv[1]
wi = int(sys.argv[2]) if len(sys.argv) > 2 else 3
case = int(sys.argv[3]) if len(sys.argv) > 3 else 4
cap = int(sys.argv[4]) if len(sys.argv) > 4 else 20480

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


def isop(x, y):
    c = g(x, y)
    return c != " " and c not in TURN


seq = []
for line in (p.stdout or "").splitlines():
    parts = line.split("|")
    if len(parts) > wi + 1:
        f = parts[wi + 1].split()
        if len(f) >= 2:
            seq.append((int(f[0]), int(f[1])))

vert = horiz = 0
pairs = collections.Counter()
runs = 0
i = 0
while i < len(seq):
    if isop(*seq[i]):
        i += 1
        continue
    j = i
    while j < len(seq) and not isop(*seq[j]):
        j += 1
    runs += 1
    for k in range(i, j - 1):
        if seq[k][1] != seq[k + 1][1]:
            vert += 1
        elif seq[k][0] != seq[k + 1][0]:
            horiz += 1
    y0, y1 = seq[i][1], seq[j - 1][1]
    if y0 != y1:
        pairs[(y0, y1)] += j - i
    i = j

print(f"walker {wi}: {len(seq)} ticks, {runs} glide runs")
print(f"  vertical steps {vert}, horizontal steps {horiz}, "
      f"stalled/other {sum(pairs.values()) and ''}")
print("--- row jumps by total cost (from_row -> to_row : glide ticks, |dy|)")
for (a, b), c in pairs.most_common(18):
    print(f"  {a:3d} -> {b:3d}  cost {c:5d}  |dy|={abs(b - a)}")
print(f"  TOTAL row-changing glide ticks {sum(pairs.values())}")
