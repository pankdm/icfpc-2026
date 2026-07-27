#!/usr/bin/env python3
"""How many controller rows are actually NEEDED?

Each emitted block owns a row, but a block only ever occupies the columns its
walker traverses on that row.  Two blocks may share one row when
  (a) their traversed column intervals are disjoint, and
  (b) neither row is crossed by a vertical highway the other needs,
because the man enters at his own highway column and turns off the row before
reaching the other block.

This measures interval (a) from the trace and greedily packs rows, reporting the
achievable row count.  Rows saved come off BOTH the box height and every
vertical transit that crossed them, so the prize is counted twice.

  python3 snake3_pack.py <man> [walker] [case] [cap]
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

rows_txt = open(man).read().split("\n")
W = max(len(r) for r in rows_txt)
rows_txt = [r.ljust(W) for r in rows_txt]

visited = collections.defaultdict(set)
for line in (p.stdout or "").splitlines():
    parts = line.split("|")
    if len(parts) > wi + 1:
        f = parts[wi + 1].split()
        if len(f) >= 2:
            visited[int(f[1])].add(int(f[0]))

# Vertical highway columns actually used: a column the walker occupies on 3+
# consecutive rows is a wire, and a row it passes through must stay clear there.
occ = {y: (min(cs), max(cs)) for y, cs in visited.items() if cs}
ys = sorted(occ)
print(f"walker {wi}: {len(ys)} rows traversed")
print("  row  [lo,hi]  width")
for y in ys:
    lo, hi = occ[y]
    print(f"  {y:3d}  [{lo:2d},{hi:2d}]  {hi - lo + 1:3d}")

# Greedy interval packing: sort by width descending, place each row in the first
# bin whose members are all column-disjoint from it.
bins = []
for y in sorted(ys, key=lambda y: -(occ[y][1] - occ[y][0])):
    lo, hi = occ[y]
    for b in bins:
        if all(hi < occ[o][0] - 1 or lo > occ[o][1] + 1 for o in b):
            b.append(y)
            break
    else:
        bins.append([y])
print(f"--- {len(ys)} traversed rows pack into {len(bins)} rows "
      f"({len(ys) - len(bins)} saved)")
multi = [b for b in bins if len(b) > 1]
print(f"    {len(multi)} shared rows, e.g.:")
for b in multi[:10]:
    print("      " + " + ".join(f"{y}{list(occ[y])}" for y in sorted(b)))
