#!/usr/bin/env python3
"""Rank the walk's pure-travel runs: consecutive executed cells with no operation.

This is the generalisation of the find that gave patch12: a stretch of the walk
carrying no op is travel that only geometry justifies, and its cost is
run_length x how often the walk takes it.  The profiler's loop ranking misses
these when they sit on a cold-ish edge, so rank them separately.

  python3 scratchpad/gbrelayout/glides.py <man> [top-n]
"""
import collections, json, os, subprocess, sys

REPO = "/Users/visenbaev/icfpc26"
LM = os.path.join(REPO, "interp", "target", "release", "lm")
man = sys.argv[1]
topn = int(sys.argv[2]) if len(sys.argv) > 2 else 15

spec = json.load(open(os.path.join(REPO, "tests", "gradebook.json")))
tc = spec["publicTestData"][-1]
rs = tc.get("rounds") or [tc]
inp = " / ".join(" ".join(r.get("in") or []) for r in rs)
exp = " / ".join(" ".join(r.get("out") or []) for r in rs)
p = subprocess.run([LM, man, "--trace", f"--input={inp}", f"--expected={exp}", "--cap=5000000"],
                   capture_output=True, text=True)
seq = []
for line in (p.stdout or "").splitlines():
    q = line.split("|")
    if len(q) >= 2 and len(q[1].split()) >= 2:
        f = q[1].split()
        seq.append((int(f[0]), int(f[1])))

rows = open(man).read().split("\n")
w = max(len(r) for r in rows)
rows = [r.ljust(w) for r in rows]
TURN = set("<>^v")


def isop(x, y):
    return rows[y][x] not in " " and rows[y][x] not in TURN


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

scored = sorted(((n * L, L, n, a, b) for (a, b, L), n in runs.items()), reverse=True)
print("ticks", len(seq))
for cost, L, n, a, b in scored[:topn]:
    print("cost %5d  run %3d cells x%-4d  %s -> %s" % (cost, L, n, a, b))
