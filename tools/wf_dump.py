#!/usr/bin/env python3
"""wf_dump.py — show a row window with glyphs, per-(cell,heading) reachability and ticks."""
import sys, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import walkfold as W

man = sys.argv[1]
y0, y1 = int(sys.argv[2]), int(sys.argv[3])
tracef = sys.argv[4] if len(sys.argv) > 4 else None

rows = W.load_rows(man)
g = W.Grid(rows)
succ = g.walk(g.starts()[0])
states = {}
for (c, d) in succ:
    states.setdefault(c, set()).add(W.DIRNAME[d])
cnt = {}
if tracef:
    cnt = json.load(open(tracef))["counts"]

wmax = 40
print("      " + "".join(str(x // 10 % 10) for x in range(wmax)))
print("      " + "".join(str(x % 10) for x in range(wmax)))
for y in range(y0, y1 + 1):
    line = []
    for x in range(wmax):
        ch = g.at(x, y)
        line.append(ch if ch != " " else ("." if (x, y) in states else " "))
    print(f"{y:3d}   {''.join(line)}")
print()
for y in range(y0, y1 + 1):
    items = []
    for x in range(wmax):
        if (x, y) in states:
            ch = g.at(x, y)
            t = cnt.get(f"{x},{y}", 0)
            items.append(f"{x}{ch if ch!=' ' else ''}:{''.join(sorted(states[(x,y)]))}"
                         + (f"/{t}" if cnt else ""))
    print(f"{y:3d} " + " ".join(items))
