#!/usr/bin/env python3
"""shift.py <in.man> <out.man> y0 y1 cmax dx — move every glyph at cols<=cmax in rows y0..y1 by dx.

Then grade.  Used to tighten the belt-scan loops: their `-`/`X`/literal block sits far west
of the belt band, so every lap glides over the gap twice.
"""
import sys, os, json, subprocess
REPO = "/Users/visenbaev/icfpc26"
sys.path.insert(0, os.path.join(REPO, "tools"))
os.chdir(REPO)
import walkfold as wf

src, out, y0, y1, cmin, cmax, dx = sys.argv[1], sys.argv[2], *[int(a) for a in sys.argv[3:8]]
rows = wf.load_rows(src)
g = wf.Grid(rows)
(rx0, ry0), (rx1, ry1) = g.rooms[0]["min"], g.rooms[0]["max"]
cells = [(x, y, g.at(x, y)) for y in range(y0, y1 + 1)
         for x in range(max(rx0 + 1, cmin), min(cmax, rx1 - 1) + 1) if g.at(x, y) != " "]
src_set = {(x, y) for x, y, _ in cells}
bad = [(x + dx, y) for x, y, _ in cells
       if (x + dx, y) not in src_set and g.at(x + dx, y) != " "]
print("moving", [(x, y, c) for x, y, c in cells])
if bad:
    print("COLLIDES at", bad)
    sys.exit(1)
patch = {f"{x},{y}": " " for x, y, _ in cells}
for (x, y, c) in cells:
    patch[f"{x + dx},{y}"] = c
open(out, "w").write(wf.render(wf.apply_patch(rows, patch)))
p = subprocess.run(["python3", "tools/grade_fast.py", "gradebook", out],
                   capture_output=True, text=True)
try:
    d = json.loads(p.stdout)
    print(f"{d['passed']}/{d['total']} box {d['footprint']['box']} avg {d['avgTicks']:.1f} score {d['score']:.0f}")
except Exception:
    print("grade failed", p.stdout[:300], p.stderr[:300])
