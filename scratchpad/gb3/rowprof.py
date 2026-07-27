#!/usr/bin/env python3
"""rowprof.py <man> [case-substr] [steps] — man0 tick attribution by ROW and by glyph class."""
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
cells = collections.Counter()
n = 0
for line in p.stdout:
    try:
        o = json.loads(line)
    except Exception:
        continue
    n += 1
    r = o["runners"][0]
    pos = tuple(r["pos"]) if isinstance(r.get("pos"), list) else (r.get("x"), r.get("y"))
    cells[pos] += 1
p.stdout.close(); p.wait()
rows = open(man).read().split("\n")


def ch(x, y):
    return rows[y][x] if y < len(rows) and x < len(rows[y]) else " "


byrow = collections.Counter()
blank = collections.Counter()
for (x, y), t in cells.items():
    byrow[y] += t
    if ch(x, y) == " ":
        blank[y] += t
tot = sum(byrow.values())
print(f"man0 ticks {tot} over {n} snapshots")
print(f"blank-glide ticks {sum(blank.values())} ({100*sum(blank.values())/tot:.1f}%)")
for y in sorted(byrow, key=lambda k: -byrow[k]):
    if byrow[y] < tot * 0.005:
        continue
    print(f" row {y:2d}: {byrow[y]:6d} ({100*byrow[y]/tot:4.1f}%) blank {blank[y]:6d}")
