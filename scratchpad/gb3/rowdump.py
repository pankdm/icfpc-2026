#!/usr/bin/env python3
"""rowdump.py <man> — per-row glyph census of room0, to find rows worth killing."""
import sys, os
REPO = "/Users/visenbaev/icfpc26"
sys.path.insert(0, os.path.join(REPO, "tools"))
os.chdir(REPO)
import walkfold as wf

rows = wf.load_rows(sys.argv[1])
g = wf.Grid(rows)
(x0, y0), (x1, y1) = g.rooms[0]["min"], g.rooms[0]["max"]
succ = g.walk(g.starts()[0])
st = wf.state_map(succ)
OPS = set("rsqSRUMNWXY%/*+-`0123456789.H@")
for y in range(y0 + 1, y1):
    cells = [(x, g.at(x, y)) for x in range(x0 + 1, x1) if g.at(x, y) != " "]
    ops = [c for c in cells if c[1] in OPS]
    turns = [c for c in cells if c[1] in "><^vV"]
    print(f"row {y:2d} n={len(cells):2d} ops={len(ops):2d} "
          f"span={min(c[0] for c in cells) if cells else '-'}-{max(c[0] for c in cells) if cells else '-'} "
          + " ".join(f"{ch}@{x}" for x, ch in cells))
