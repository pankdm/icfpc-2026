#!/usr/bin/env python3
"""Per-walker glide-run ranking for snake.

A glide run = consecutive executed cells carrying NO operation (blank or a pure
turn arrow).  Its cost is run_length x how often the walk takes it.  Loop
profilers miss these because a run spans loop boundaries.

Two corrections that matter on a multi-man program:
  * split PER WALKER -- mixing walkers makes every run an artefact;
  * a walker that parks blocked on `r` has FREE slack, so only the walker whose
    lap IS the program's period is worth optimising.  This prints, per walker,
    how many ticks it actually MOVED, so the parked ones are obvious.

  python3 snake3_glides.py <man> [case_index] [top-n]
"""
import collections
import json
import os
import subprocess
import sys

REPO = "/Users/visenbaev/icfpc26"
LM = os.path.join(REPO, "interp", "target", "release", "lm")

man = sys.argv[1]
case = int(sys.argv[2]) if len(sys.argv) > 2 else 4
topn = int(sys.argv[3]) if len(sys.argv) > 3 else 12
CAP = int(sys.argv[4]) if len(sys.argv) > 4 else 20480

spec = json.load(open(os.path.join(REPO, "tests", "snake.json")))
tc = spec["publicTestData"][case]
rs = tc.get("rounds") or [tc]
inp = " / ".join(" ".join(r.get("in") or []) for r in rs)
exp = " / ".join(" ".join(r.get("out") or []) for r in rs)
p = subprocess.run([LM, man, "--trace", f"--input={inp}", f"--expected={exp}",
                    f"--cap={CAP}"], capture_output=True, text=True)

rows = open(man).read().split("\n")
W = max(len(r) for r in rows)
rows = [r.ljust(W) for r in rows]
TURN = set("<>^v")


def isop(x, y):
    if not (0 <= y < len(rows) and 0 <= x < W):
        return False
    c = rows[y][x]
    return c != " " and c not in TURN


tracks = collections.defaultdict(list)
for line in (p.stdout or "").splitlines():
    parts = line.split("|")
    for i, seg in enumerate(parts[1:]):
        f = seg.split()
        if len(f) >= 2:
            tracks[i].append((int(f[0]), int(f[1])))

print(f"{tc['name']}: ticks {len(tracks[0])}, walkers {len(tracks)}")
for wi, seq in sorted(tracks.items()):
    moved = sum(1 for a, b in zip(seq, seq[1:]) if a != b)
    ops = sum(1 for c in seq if isop(*c))
    print(f"  walker {wi}: moved {moved}/{len(seq)} ticks, op-cells {ops}")

for wi, seq in sorted(tracks.items()):
    runs = collections.Counter()
    i = 0
    while i < len(seq):
        if isop(*seq[i]):
            i += 1
            continue
        j = i
        while j < len(seq) and not isop(*seq[j]):
            j += 1
        runs[(seq[i], seq[j - 1], j - i)] += 1
        i = j
    if not runs:
        continue
    scored = sorted(((n * L, L, n, a, b) for (a, b, L), n in runs.items()),
                    reverse=True)
    total = sum(c for c, _, _, _, _ in scored)
    print(f"--- walker {wi}: {total} glide ticks")
    for cost, L, n, a, b in scored[:topn]:
        print("  cost %5d  run %3d x%-5d  %s -> %s" % (cost, L, n, a, b))
