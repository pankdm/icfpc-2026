#!/usr/bin/env python3
"""cellprof.py <man> [case-substr] — per-cell tick attribution for every man, via lm snapshots.

Streams `lm <man> <steps>` snapshots and counts, for each man, how many ticks it spent on
each cell.  A cell with far more ticks than visits is a STALL (blocked on r/s).
"""
import json, subprocess, sys, os, collections
REPO = "/Users/visenbaev/icfpc26"
os.chdir(REPO)
man = sys.argv[1]
sub = sys.argv[2] if len(sys.argv) > 2 else "N=16"
steps = int(sys.argv[3]) if len(sys.argv) > 3 else 40000

d = json.load(open("tests/gradebook.json"))
c = [x for x in d["publicTestData"] if sub in x["name"]][0]
rs = c["rounds"]
inp = " / ".join(" ".join(r.get("in") or []) for r in rs)
exp = " / ".join(" ".join(r.get("out") or []) for r in rs)

p = subprocess.Popen(["interp/target/release/lm", man, str(steps), "--input=" + inp,
                      "--expected=" + exp, "--cap=3000000"],
                     stdout=subprocess.PIPE, text=True, bufsize=1 << 20)
cells = collections.defaultdict(collections.Counter)   # mi -> Counter[(x,y)]
prev = {}
moves = collections.defaultdict(collections.Counter)
n = 0
for line in p.stdout:
    try:
        o = json.loads(line)
    except Exception:
        continue
    n += 1
    for mi, r in enumerate(o["runners"]):
        pos = tuple(r["pos"]) if isinstance(r.get("pos"), list) else (r.get("x"), r.get("y"))
        cells[mi][pos] += 1
        if prev.get(mi) != pos:
            moves[mi][pos] += 1
        prev[mi] = pos
p.stdout.close(); p.wait()
print(f"ticks streamed: {n}")
rows = open(man).read().split("\n")


def ch(x, y):
    return rows[y][x] if y < len(rows) and x < len(rows[y]) else " "


for mi in sorted(cells):
    tot = sum(cells[mi].values())
    print(f"\n== man{mi} total {tot}")
    for (pos, t) in cells[mi].most_common(18):
        v = moves[mi][pos]
        print(f"   ({pos[0]:2d},{pos[1]:2d}) '{ch(*pos)}'  ticks={t:6d} visits={v:5d} stall={t - v:6d}")
