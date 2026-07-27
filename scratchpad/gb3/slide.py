#!/usr/bin/env python3
"""slide.py — permute which RING holds which register, by sliding pipe ops between bands.

The four ring rooms are byte-identical (`>@rv`/`^.s<`), so which physical ring holds which
logical register is decided purely by WHICH COLUMN BAND the ops that talk to it sit in.
Permuting them therefore needs no pipe rerouting whatsoever: only the `r`/`s`/`q` cells move,
each one staying inside its own straight run so the walk, the turns and the tick count are
untouched.

A run's glyphs are re-assigned greedily left-to-right (in walk order): pinned glyphs (turns,
branches, literals, and any cell more than one flow touches) hold their position, everything
else takes the first legal column at or after the cursor and inside its band.

usage: slide.py <in.man> <out.man> --in 8:26,26:8 --out 11:29,29:11
"""
import sys, os, argparse

REPO = "/Users/visenbaev/icfpc26"
sys.path.insert(0, os.path.join(REPO, "tools"))
os.chdir(REPO)
import walkfold as wf

PIPE_OPS = set("rsqSRU")
PINNED_GLYPHS = set("><^vV") | wf.BRANCH | {"`"} | set("0123456789") | {"H", "@", "Y"}


def parse_perm(s):
    if not s:
        return {}
    out = {}
    for part in s.split(","):
        a, b = part.split(":")
        out[int(a)] = int(b)
    return out


def attach_cols(g, room=0):
    inc, out = [], []
    for pi, p in enumerate(g.pipes):
        path = p.get("path") or []
        if not path:
            continue
        if p.get("src") == room:
            out.append((pi, tuple(path[0]["pos"])))
        if p.get("dst") == room:
            inc.append((pi, tuple(path[-1]["pos"])))
    return inc, out


def band_intervals(g, room=0):
    """attach-column -> inclusive column interval, for in and out separately."""
    tab, pure, inc, out = wf.bands(g, room)
    assert pure, "room0 attachments are not on one wall row"
    res = {"in": {}, "out": {}}
    colof = {"in": {pi: c[0] for pi, c in inc}, "out": {pi: c[0] for pi, c in out}}
    for kind in ("in", "out"):
        for x in sorted(tab):
            pi = tab[x][kind]
            if pi is None:
                continue
            c = colof[kind][pi]
            lo, hi = res[kind].get(c, (x, x))
            res[kind][c] = (min(lo, x), max(hi, x))
    return res, tab, colof


def runs_of(g, succ):
    """Maximal straight segments of the walk: list of (heading, [cells in order])."""
    pred = {}
    for s, ns in succ.items():
        for n in ns:
            pred.setdefault(n, []).append(s)
    out = []
    seen = set()
    for s in succ:
        cell, d = s
        back = ((cell[0] - d[0], cell[1] - d[1]), d)
        if back in succ and s in succ.get(back, ()):
            continue                                  # not a run start
        if s in seen:
            continue
        cells, cur = [], s
        while True:
            seen.add(cur)
            cells.append(cur[0])
            nxt = ((cur[0][0] + d[0], cur[0][1] + d[1]), d)
            if nxt in succ.get(cur, ()) and nxt in succ:
                cur = nxt
            else:
                if nxt in succ.get(cur, ()):
                    cells.append(nxt[0])
                break
        out.append((d, cells))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("man")
    ap.add_argument("out")
    ap.add_argument("--in", dest="pin", default="")
    ap.add_argument("--out", dest="pout", default="")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    perm = {"in": parse_perm(a.pin), "out": parse_perm(a.pout)}

    rows = wf.load_rows(a.man)
    g = wf.Grid(rows)
    succ = g.walk(g.starts()[0])
    st = wf.state_map(succ)
    bands, tab, colof = band_intervals(g)
    (rx0, ry0), (rx1, ry1) = g.rooms[0]["min"], g.rooms[0]["max"]

    def movable(cell, d):
        ch = g.at(*cell)
        if ch in PINNED_GLYPHS or ch == " ":
            return False
        if st.get(cell, set()) != {d}:
            return False
        return True

    def free_for_glyph(cell, d):
        return g.at(*cell) == " " and st.get(cell, set()) == {d}

    patch, moved, refused = {}, 0, []
    for d, cells in runs_of(g, succ):
        if d[1] != 0:
            continue                                   # vertical runs: nothing to slide
        inside = [c for c in cells if rx0 < c[0] < rx1 and ry0 < c[1] < ry1]
        if not inside:
            continue
        seq = [c for c in inside if g.at(*c) != " "]
        if not any(g.at(*c) in PIPE_OPS and movable(c, d) for c in seq):
            continue
        lo_x, hi_x = min(c[0] for c in inside), max(c[0] for c in inside)
        step = d[0]
        y = inside[0][1]
        u = lambda x: x * step                          # walk coordinate: increases forward
        order = sorted(inside, key=lambda c: u(c[0]))
        cursor = None
        plan = []
        ok = True
        for cell in order:
            ch = g.at(*cell)
            if ch == " ":
                continue
            if not movable(cell, d):
                if cursor is not None and u(cell[0]) <= cursor:
                    ok = False
                    break
                cursor = u(cell[0])
                plan.append((cell, ch, cell[0]))
                continue
            if ch in PIPE_OPS:
                kind = "out" if ch in "sS" else "in"
                old = colof[kind][tab[cell[0]][kind]]
                new = perm[kind].get(old, old)
                blo, bhi = bands[kind][new]
            else:
                blo, bhi = lo_x, hi_x
            lo, hi = max(blo, lo_x), min(bhi, hi_x)
            if lo > hi:
                ok = False
                refused.append((cell, ch, "band outside run"))
                break
            ulo, uhi = min(u(lo), u(hi)), max(u(lo), u(hi))
            if cursor is not None:
                ulo = max(ulo, cursor + 1)
            cand = None
            for uu in range(ulo, uhi + 1):
                c2 = (uu * step, y)
                if c2 == cell or free_for_glyph(c2, d):
                    cand = uu * step
                    break
            if cand is None:
                ok = False
                refused.append((cell, ch, (blo, bhi)))
                break
            cursor = u(cand)
            plan.append((cell, ch, cand))
        if not ok:
            refused.append(("run", cells[0], d))
            continue
        for (cell, ch, nx) in plan:
            if nx != cell[0]:
                patch[f"{cell[0]},{cell[1]}"] = " "
        for (cell, ch, nx) in plan:
            if nx != cell[0]:
                patch[f"{nx},{cell[1]}"] = ch
                moved += 1

    newrows = wf.apply_patch(rows, patch)
    open(a.out, "w").write(wf.render(newrows))
    print(f"wrote {a.out}: {moved} ops moved, {len(refused)} refusals")
    if a.verbose:
        for r in refused[:20]:
            print("   refused", r)


main()
