#!/usr/bin/env python3
"""colprof.py <man> [case] [steps] — man0 ticks by COLUMN, split blank vs glyph."""
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
for line in p.stdout:
    try:
        o = json.loads(line)
    except Exception:
        continue
    r = o["runners"][0]
    pos = tuple(r["pos"]) if isinstance(r.get("pos"), list) else (r.get("x"), r.get("y"))
    cells[pos] += 1
p.stdout.close(); p.wait()
rows = open(man).read().split("\n")


def ch(x, y):
    return rows[y][x] if y < len(rows) and x < len(rows[y]) else " "


bycol = collections.Counter(); blank = collections.Counter()
for (x, y), t in cells.items():
    bycol[x] += t
    if ch(x, y) == " ":
        blank[x] += t
tot = sum(bycol.values())
print(f"total {tot}  blank {sum(blank.values())}")
for x in sorted(bycol):
    print(f" col {x:2d}: {bycol[x]:6d} blank {blank[x]:6d}")
print("\nblank cells top 25:")
for (pos, t) in sorted(((p, t) for p, t in cells.items() if ch(*p) == " "), key=lambda kv: -kv[1])[:25]:
    print(f"   ({pos[0]:2d},{pos[1]:2d}) {t}")
