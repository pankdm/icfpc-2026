#!/usr/bin/env python3
"""vfuse — merge two ADJACENT interior rows of a room into one, deleting a row.

Different from walkfold's `fuse` (which appends a code row to a previous row of the same
heading) and from `squash` (which only deletes rows with no glyph at all).  Here rows y and
y+1 collapse onto one another when the static walk analysis proves they cannot interfere:

  (a) no column carries a glyph in BOTH rows            — else the merged cell is ambiguous
  (b) no glyph of row y+1 sits on a cell row y traverses HORIZONTALLY, and vice versa
      — a horizontal glide onto a glyph executes it

Vertical traversals are safe for free: a man crossing both rows in one column meets the same
(at most one) glyph before and after, he just spends one tick less doing it.

Usage: gb_vfuse.py <in.man> [out.man]      — reports every legal pair, applies them all
"""
import os
import sys

REPO = "/Users/dmitrykorolev/projects/icfpc-2026-main"
sys.path.insert(0, os.path.join(REPO, "tools"))
import walkfold as wf  # noqa: E402


def analyse(path):
    rows = wf.load_rows(path)
    g = wf.Grid(rows)
    horiz, vert = {}, {}
    for st in g.starts():
        for ((x, y), d) in g.walk(st):
            (horiz if d[1] == 0 else vert).setdefault(y, set()).add(x)
    occ = {}
    for y, r in enumerate(rows):
        occ[y] = {x for x, c in enumerate(r) if c != " "}
    return rows, g, horiz, vert, occ


def interior_rows(g):
    out = {}
    for i, r in enumerate(g.rooms):
        (x0, y0), (x1, y1) = r["min"], r["max"]
        for y in range(y0 + 1, y1):
            out.setdefault(i, []).append((y, x0, x1))
    return out


def main():
    path = sys.argv[1]
    rows, g, horiz, vert, occ = analyse(path)
    ir = interior_rows(g)
    pairs = []
    for rid, lst in ir.items():
        ys = [y for (y, _, _) in lst]
        x0, x1 = lst[0][1], lst[0][2]
        inner = lambda s: {x for x in s if x0 < x < x1}  # noqa: E731
        for y in ys:
            if y + 1 not in ys:
                continue
            a, b = inner(occ[y]), inner(occ[y + 1])
            ha, hb = inner(horiz.get(y, set())), inner(horiz.get(y + 1, set()))
            why = []
            if a & b:
                why.append(f"glyph clash cols {sorted(a & b)}")
            if ha & b:
                why.append(f"row{y} glides over row{y+1} glyphs {sorted(ha & b)}")
            if hb & a:
                why.append(f"row{y+1} glides over row{y} glyphs {sorted(hb & a)}")
            if not why:
                pairs.append((rid, y))
                print(f"MERGEABLE room{rid} rows {y}+{y+1}")
            else:
                print(f"  no  room{rid} rows {y}+{y+1}: {'; '.join(why)}")
    print(f"\n{len(pairs)} mergeable pair(s)")
    if not pairs or len(sys.argv) < 3:
        return
    # apply, greedily, skipping overlaps
    doomed, prev = [], -99
    for (_, y) in pairs:
        if y <= prev + 1:
            continue
        doomed.append(y + 1)
        prev = y + 1
    out = [list(r) for r in rows]
    for y in doomed:
        for x, c in enumerate(out[y]):
            if c != " ":
                out[y - 1][x] = c
    keep = [r for i, r in enumerate(out) if i not in set(doomed)]
    open(sys.argv[2], "w").write(wf.render(keep))
    print(f"deleted rows {doomed} -> {sys.argv[2]}")


main()

# MEASURED 2026-07-27 on the live champion (61x71, box 5041, commit 089b211):
#   0 mergeable pairs out of 63 interior rows of room0.  Four pairs (22+23, 28+29,
#   45+46, 57+58) have NO glyph clash and fail only on the glide test: every one of
#   room0's connector rows is a single long horizontal run (span averages 34 of 59
#   columns) that sweeps straight across its neighbour's ops.  The blocking glyphs are
#   always the landing cells of vertical spines, whose columns are pinned by the block
#   that sends the man down them, so none of them can be slid aside either.
