#!/usr/bin/env python3
"""Bound the prize from REORDERING the controller's block rows.

The emitted controller pays |row_a - row_b| vertical travel for every jump
between two blocks, and the row of each block is just its emission order --
a dimension the column knobs (HW_*, D_*, DRVX, CW) cannot reach.

This builds the observed row-jump graph for one walker and anneals a row
permutation minimising  sum(freq * |pos(a) - pos(b)|).  The reported delta is
the vertical-travel saving an ideal reordering would buy, i.e. an upper bound
on what a row-reordered emitter is worth.

  python3 snake3_arrange.py <man> [walker] [case] [cap]
"""
import collections
import json
import math
import os
import random
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


def isop(x, y):
    c = rows[y][x] if 0 <= y < len(rows) and 0 <= x < W else " "
    return c != " " and c not in TURN


seq = []
for line in (p.stdout or "").splitlines():
    parts = line.split("|")
    if len(parts) > wi + 1:
        f = parts[wi + 1].split()
        if len(f) >= 2:
            seq.append((int(f[0]), int(f[1])))

# Jump graph: consecutive OP rows that differ (the glide between them is travel).
jumps = collections.Counter()
prev_row = None
for x, y in seq:
    if isop(x, y):
        if prev_row is not None and prev_row != y:
            a, b = (prev_row, y) if prev_row < y else (y, prev_row)
            jumps[(a, b)] += 1
        prev_row = y

used = sorted({r for pair in jumps for r in pair})
idx = {r: i for i, r in enumerate(used)}
n = len(used)
cur_cost = sum(f * abs(a - b) for (a, b), f in jumps.items())
print(f"walker {wi}: {n} distinct op rows, {len(jumps)} jump pairs")
print(f"  vertical travel as laid out: {cur_cost} ticks")

edges = [(idx[a], idx[b], f) for (a, b), f in jumps.items()]
# Row heights are not uniform; use the observed spacing so a permutation is
# scored on real cells, not slot indices.
span = [used[i + 1] - used[i] for i in range(n - 1)] + [1]


def cost(order):
    pos = {}
    y = 0
    for slot, node in enumerate(order):
        pos[node] = y
        y += span[slot]
    return sum(f * abs(pos[a] - pos[b]) for a, b, f in edges)


rng = random.Random(7)
best = list(range(n))
bcost = cost(best)
for restart in range(6):
    order = list(range(n))
    rng.shuffle(order)
    c = cost(order)
    for it in range(60000):
        T = 40.0 * (1 - it / 60000) + 0.5
        i, j = rng.randrange(n), rng.randrange(n)
        if i == j:
            continue
        order[i], order[j] = order[j], order[i]
        c2 = cost(order)
        if c2 <= c or rng.random() < math.exp((c - c2) / T):
            c = c2
            if c2 < bcost:
                bcost, best = c2, list(order)
        else:
            order[i], order[j] = order[j], order[i]
print(f"  best reordering:            {bcost} ticks "
      f"({cur_cost - bcost} saved, {100 * (cur_cost - bcost) / max(cur_cost, 1):.1f}%)")
print(f"  => period {len(seq)} -> {len(seq) - (cur_cost - bcost)} "
      f"({len(seq) / max(len(seq) - (cur_cost - bcost), 1):.3f}x on this case)")
print("--- heaviest pairs (freq x |dy|)")
for (a, b), f in sorted(jumps.items(), key=lambda t: -t[1] * abs(t[0][0] - t[0][1]))[:12]:
    print(f"  {a:3d} <-> {b:3d}  freq {f:5d}  |dy| {abs(a - b):3d}  cost {f * abs(a - b):6d}")
