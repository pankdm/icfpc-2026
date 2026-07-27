#!/usr/bin/env python3
"""Per-row glyph census of room0 for a gradebook grid."""
import sys, os
sys.path.insert(0, "/Users/visenbaev/icfpc26/tools")
import walkfold as W

man = sys.argv[1]
rows = W.load_rows(man)
g = W.Grid(rows)
succ = g.walk(g.starts()[0])
st = W.state_map(succ)
(x0, y0), (x1, y1) = g.rooms[0]["min"], g.rooms[0]["max"]
for y in range(y0 + 1, y1):
    cols = [x for x in range(x0 + 1, x1) if g.at(x, y) != " "]
    dirs = set()
    for x in range(x0 + 1, x1):
        for d in st.get((x, y), ()):
            dirs.add(W.DIRNAME[d])
    ncov = len([x for x in range(x0 + 1, x1) if (x, y) in st])
    glyphs = "".join(g.at(x, y) for x in cols)
    rng = f"{min(cols)}-{max(cols)}" if cols else "-"
    print(f"{y:3d} n={len(cols):2d} span={rng:>7} cov={ncov:2d} dirs={''.join(sorted(dirs)):4} {glyphs}")
