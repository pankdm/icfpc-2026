#!/usr/bin/env python3
"""Top cells by executed-tick count, per walker.

On a multi-man program a big count on `r`/`s` is a STALL, not work: the walker
sat there waiting for a pipe.  Ranking cells this way separates the two costs
that geometry cannot fix (latency, contention) from the ones it can (travel).

  python3 snake3_cells.py <man> [case] [cap] [top-n]
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
cap = int(sys.argv[3]) if len(sys.argv) > 3 else 20480
topn = int(sys.argv[4]) if len(sys.argv) > 4 else 12

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

hits = collections.defaultdict(collections.Counter)
prev = {}
stalls = collections.defaultdict(collections.Counter)
for line in (p.stdout or "").splitlines():
    parts = line.split("|")
    for wi, seg in enumerate(parts[1:]):
        f = seg.split()
        if len(f) < 2:
            continue
        c = (int(f[0]), int(f[1]))
        hits[wi][c] += 1
        if prev.get(wi) == c:
            stalls[wi][c] += 1
        prev[wi] = c

for wi in sorted(hits):
    tot = sum(hits[wi].values())
    st = sum(stalls[wi].values())
    print(f"walker {wi}: {tot} ticks, {st} of them re-executing the same cell (stall)")
    for c, n in hits[wi].most_common(topn):
        ch = rows[c[1]][c[0]]
        print(f"    {c} {ch!r}  {n:6d}  stalled {stalls[wi][c]:6d}")
