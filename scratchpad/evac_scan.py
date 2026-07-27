#!/usr/bin/env python3
"""throwaway: how many lines are actually evacuable, and what blocks the rest."""
import sys, os
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
import place as P

TARGETS = [
    ("matmul", "solutions/matmul/live-9fb4b626.man"),
    ("gradebook", "solutions/gradebook/live-1bb8b72f.man"),
    ("snake", "solutions/snake/live-3887adaf.man"),
    ("subset-sum", "solutions/subset-sum/live-350d15b4.man"),
]

for slug, rel in TARGETS:
    path = os.path.join(REPO, rel)
    plan = P.Plan(path)
    rows = plan.rows
    H = len(rows)
    W = max(len(r) for r in rows)
    ys = [y for y in range(H) if rows[y].strip()]
    xs = [x for x in range(W) if any(len(r) > x and r[x] != " " for r in rows)]
    print(f"\n=== {slug}  {xs[-1]-xs[0]+1}x{ys[-1]-ys[0]+1}  blocks={len(plan.blocks)} "
          f"pipes={len(plan.pipes)} orphans={len(plan.orphans)}")

    # cell -> owner
    blockcells = set()
    for b in plan.blocks:
        x0, y0, x1, y1 = b.rect(b.ox0, b.oy0)
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                blockcells.add((x, y))
    pipecell = {}
    for p in plan.pipes:
        for c in p.cells:
            pipecell[c] = p.idx

    for axis in ("row", "col"):
        cands = []
        for idx in (range(ys[0], ys[-1] + 1) if axis == "row" else range(xs[0], xs[-1] + 1)):
            def on(c):
                return c[1] == idx if axis == "row" else c[0] == idx
            if any(on(c) for c in blockcells):
                continue
            if any(on(c) for c in plan.orphans):
                continue
            touching = sorted({pipecell[c] for c in pipecell if on(c)})
            # spanning pipes: src block and dst block on opposite sides
            span = []
            for p in plan.pipes:
                sb = plan.blocks[p.src_b]
                db = plan.blocks[p.dst_b]
                sa = (sb.oy0 if axis == "row" else sb.ox0)
                sh = (sb.h if axis == "row" else sb.w)
                da = (db.oy0 if axis == "row" else db.ox0)
                dh = (db.h if axis == "row" else db.w)
                s_side = -1 if sa + sh - 1 < idx else 1
                d_side = -1 if da + dh - 1 < idx else 1
                if s_side != d_side:
                    span.append(p.idx)
            cands.append((idx, touching, span))
        print(f"  {axis}s: {len(cands)} pipe-only")
        clean = [c for c in cands if not c[2]]
        print(f"     of which NO spanning pipe: {len(clean)} -> {[c[0] for c in clean]}")
        for idx, touching, span in cands[:60]:
            print(f"       {axis} {idx}: pipes_on_line={touching} spanning={span}")
