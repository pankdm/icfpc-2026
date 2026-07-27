#!/usr/bin/env python3
"""narrow_room.py — shave columns off ONE room by deleting a BLANK cell per row.

Why this and not a re-emit: the champion controllers here are imported, hand-folded
boustrophedons.  Re-laying one from the lifted flow (flowgrid) rebuilds all the
control-flow routing and changes the walk, hence the ticks.  This pass instead keeps every
op in the same ORDER and the same ROW, and merely deletes one blank cell per row, sliding
that row's suffix one column left.  The man walks one cell FEWER on each shortened row, so
ticks can only fall, and `max(w,h)` falls by one.

Two things can break, and both are constraints in the model rather than hopes:

  1. a VERTICAL move: `v` at (x,y) hands control to (x,y+1), so rows y and y+1 must agree
     on whether column x slid.  Links are read off the static walk's TRANSITIONS (not the
     states' own headings — a branch is entered eastward and leaves vertically, so the
     heading of the branch cell does not reveal the link it creates);
  2. PIPE RE-BINDING: `s`/`r`/`q` lock onto the nearest attach cell by Manhattan distance
     with reading-order ties, so an op that slides one column left may silently change
     which pipe it talks to.  Every such op is re-resolved at its destination with
     liftflow's own `_bind` (the engine's rule verbatim) and pinned if it would move.

    python3 scratchpad/narrow_room.py <in.man> <out.man> [--cols N] [--room I]
"""
import argparse
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
import lift as _lift          # noqa: E402
import liftflow as _lf        # noqa: E402

SEND, RECV = set("s"), set("rq")


def load(path):
    text = open(path, encoding="utf-8").read().replace("\r", "").rstrip("\n")
    rows = text.split("\n")
    w = max(len(r) for r in rows)
    return [list(r.ljust(w)) for r in rows], w


def vertical_links(lf):
    """{(x, y)}: rows y and y+1 are joined by a vertical move at column x, over EVERY man."""
    links = set()
    for start in lf.starts():
        states, trans = _lf._walk_states(lf, start)
        for st, outs in trans.items():
            (x, y), _ = st
            for (nx, ny), _nd in outs:
                if ny != y:
                    links.add((x, min(y, ny)))
    return links


def attach_list(lf, room, newcols=None):
    raw = []
    for i, p in enumerate(lf.pipes):
        if p["src"] == room:
            a = p["path"][0]["pos"]
            raw.append((f"o{i}", (newcols or {}).get(i, a[0]), a[1], "s", i))
        if p["dst"] == room:
            a = p["path"][-1]["pos"]
            raw.append((f"i{i}", (newcols or {}).get(i, a[0]), a[1], "r", i))
    return raw


def pin_ops(lf, grid, room, x_lo, x_hi, y_lo, y_hi, shift, newcols):
    """Per pipe op: may it stay, may it slide?  Judged against its ORIGINAL binding, with
    the destination pipe geometry (`newcols`) in force.  Returns (must_slide, must_stay,
    infeasible) as {row: [columns]}."""
    old = attach_list(lf, room)
    new = attach_list(lf, room, newcols)
    must_slide, must_stay, bad = {}, {}, []
    for y in range(y_lo, y_hi + 1):
        for x in range(x_lo, x_hi + 1):
            ch = grid[y][x]
            grp = "s" if ch in SEND else ("r" if ch in RECV else None)
            if grp is None:
                continue
            want = _lf._bind((x, y), old, grp)
            stay = _lf._bind((x, y), new, grp) == want
            slid = all(_lf._bind((x - k, y), new, grp) == want for k in range(1, shift + 1))
            if not stay and not slid:
                bad.append((x, y, want))
            elif not stay:
                must_slide.setdefault(y, []).append(x)
            elif not slid:
                must_stay.setdefault(y, []).append(x)
    return must_slide, must_stay, bad


def solve_cuts(grid, rows_ix, x_lo, x_hi, links, ncols, must_slide, must_stay):
    """cut[y][k] = column of the k-th deleted blank cell in row y (strictly increasing).
    A cell at column c slides left by |{k : cut[y][k] < c}|."""
    import z3
    opt = z3.Optimize()
    cuts = {}
    for y in rows_ix:
        blanks = [c for c in range(x_lo, x_hi + 1) if grid[y][c] == " "]
        if len(blanks) < ncols:
            return None, f"row {y}: only {len(blanks)} blank interior cells, need {ncols}"
        vs = [z3.Int(f"c_{y}_{k}") for k in range(ncols)]
        cuts[y] = vs
        for k, v in enumerate(vs):
            opt.add(z3.Or([v == b for b in blanks]))
            if k:
                opt.add(vs[k - 1] < v)

    def slide(y, x):
        return z3.Sum([z3.If(v < x, 1, 0) for v in cuts[y]])

    for (x, y) in links:
        a, b = (y in cuts), (y + 1 in cuts)
        if a and b:
            opt.add(slide(y, x) == slide(y + 1, x))
        elif a:
            opt.add(slide(y, x) == 0)
        elif b:
            opt.add(slide(y + 1, x) == 0)
    npin = 0
    for y, lst in must_stay.items():
        for x in lst:
            if y in cuts:
                opt.add(slide(y, x) == 0)
                npin += 1
    for y, lst in must_slide.items():
        for x in lst:
            if y in cuts:
                opt.add(slide(y, x) == ncols)
                npin += 1
    opt.maximize(z3.Sum([z3.Sum(vs) for vs in cuts.values()]))
    print(f"model: {len(cuts)} rows x {ncols} cuts, {len(links)} link constraints, "
          f"{npin} pipe-binding pins")
    if opt.check() != z3.sat:
        return None, "UNSAT"
    m = opt.model()
    return {y: sorted(m[v].as_long() for v in vs) for y, vs in cuts.items()}, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--cols", type=int, default=1)
    ap.add_argument("--room", type=int, default=0)
    ap.add_argument("--pipe-cols", default="",
                    help="assume pipe attach columns move, e.g. '1:29' (the grid edit that "
                         "realises the move is a separate step; this only re-judges binding)")
    args = ap.parse_args()

    newcols = {}
    for part in filter(None, args.pipe_cols.split(",")):
        i, c = part.split(":")
        newcols[int(i)] = int(c)

    grid, w = load(args.src)
    lf = _lift.Lift(_lift.load_rows(args.src))
    (rx0, ry0), (rx1, ry1) = lf.rooms[args.room]["min"], lf.rooms[args.room]["max"]
    print(f"room {args.room}: ({rx0},{ry0})-({rx1},{ry1})  grid {w}x{len(grid)}")
    interior = list(range(ry0 + 1, ry1))
    links = vertical_links(lf)
    ms, mst, bad = pin_ops(lf, grid, args.room, rx0 + 1, rx1 - 1, ry0 + 1, ry1 - 1,
                           args.cols, newcols)
    if bad:
        cols = sorted({x for x, y, _ in bad})
        sys.exit(f"{len(bad)} pipe ops can neither stay nor slide (columns {cols}) — "
                 f"no cut plan exists with these pipe columns")
    print(f"pipe ops: {sum(len(v) for v in ms.values())} must slide, "
          f"{sum(len(v) for v in mst.values())} must stay")
    cuts, err = solve_cuts(grid, interior, rx0 + 1, rx1 - 1, links, args.cols, ms, mst)
    if cuts is None:
        sys.exit(f"no cut plan: {err}")
    for y in (ry0, ry1):
        cuts[y] = list(range(rx1 - args.cols, rx1))
    out = []
    for y, row in enumerate(grid):
        drop = set(cuts.get(y, ()))
        out.append("".join(row[c] for c in range(w) if c not in drop))
    txt = "\n".join(r.rstrip() for r in out) + "\n"
    open(args.dst, "w").write(txt)
    lines = txt.rstrip("\n").split("\n")
    nw, nh = max(len(r) for r in lines), len(lines)
    print(f"wrote {args.dst}: {nw}x{nh}  box {max(nw, nh) ** 2:,}")
    lo = min(min(v) for y, v in cuts.items() if y in interior)
    print(f"leftmost cut column {lo}")


if __name__ == "__main__":
    main()
