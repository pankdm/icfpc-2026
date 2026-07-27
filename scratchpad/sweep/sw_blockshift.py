#!/usr/bin/env python3
"""blockshift generalised to any slug and to EVERY room, not just rooms[0].

A candidate is a column range [a,b] inside a row window of one room whose bounding
columns a-1 and b+1 are blank on every row of the window -- so the block is not
welded to anything -- shifted by dx into cells that are all blank.  Every candidate
is graded through sw_gradelib.Gate (public + every stress suite for the slug) and
kept only if nothing fails and the score strictly improves.

usage: sw_blockshift.py <slug> <in.man> <out.man> [--rounds N] [--jobs N]
                        [--maxh N] [--maxw N] [--maxdx N] [--pub-cap N]
"""
import sys, os, json, argparse, tempfile, concurrent.futures

REPO = "/Users/visenbaev/icfpc26"
sys.path.insert(0, os.path.join(REPO, "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
import walkfold as wf
import sw_gradelib


def vprops(g, maxh, maxw, maxdy):
    """Vertical twin of props(): a ROW range [ya,yb] inside a column window whose
    bounding rows ya-1 and yb+1 are blank across the window, slid by dy.  The
    original tool only ever shifted horizontally, so on a grid whose hot glide
    corridors run vertically it has nothing to propose."""
    out = []
    for room in g.rooms:
        (x0, y0), (x1, y1) = room["min"], room["max"]
        for xa in range(x0 + 1, x1):
            for w in range(1, maxw + 1):
                xb = xa + w - 1
                if xb >= x1:
                    break
                xs = range(xa, xb + 1)
                for ya in range(y0 + 1, y1):
                    if ya > y0 + 1 and any(g.at(x, ya - 1) != " " for x in xs):
                        continue
                    for yb in range(ya, min(ya + maxh, y1 - 1) + 1):
                        if any(g.at(x, yb + 1) != " " for x in xs):
                            continue
                        cells = [(x, y, g.at(x, y)) for y in range(ya, yb + 1)
                                 for x in xs if g.at(x, y) != " "]
                        if not cells:
                            continue
                        for dy in (list(range(1, maxdy + 1))
                                   + list(range(-1, -maxdy - 1, -1))):
                            if not (y0 < ya + dy and yb + dy < y1):
                                continue
                            if any(g.at(x, y + dy) != " " for x in xs
                                   for y in range(ya, yb + 1)
                                   if not (ya <= y + dy <= yb)):
                                continue
                            p = {"%d,%d" % (x, y): " " for x, y, _ in cells}
                            for (x, y, c) in cells:
                                p["%d,%d" % (x, y + dy)] = c
                            out.append(("vblk[%d-%d]x[%d-%d]%+d" % (xa, xb, ya, yb, dy), p))
    return out


def props(g, maxh, maxw, maxdx):
    """All isolated-rectangle shifts, over every room in the grid."""
    out = []
    for room in g.rooms:
        (x0, y0), (x1, y1) = room["min"], room["max"]
        for ya in range(y0 + 1, y1):
            for h in range(1, maxh + 1):
                yb = ya + h - 1
                if yb >= y1:
                    break
                ys = range(ya, yb + 1)
                for a in range(x0 + 1, x1):
                    if a > x0 + 1 and any(g.at(a - 1, y) != " " for y in ys):
                        continue
                    for b in range(a, min(a + maxw, x1 - 1) + 1):
                        if any(g.at(b + 1, y) != " " for y in ys):
                            continue
                        cells = [(x, y, g.at(x, y)) for y in ys
                                 for x in range(a, b + 1) if g.at(x, y) != " "]
                        if not cells:
                            continue
                        for dx in (list(range(1, maxdx + 1))
                                   + list(range(-1, -maxdx - 1, -1))):
                            if not (x0 < a + dx and b + dx < x1):
                                continue
                            if any(g.at(x + dx, y) != " " for y in ys
                                   for x in range(a, b + 1)
                                   if not (a <= x + dx <= b)):
                                continue
                            p = {"%d,%d" % (x, y): " " for x, y, _ in cells}
                            for (x, y, c) in cells:
                                p["%d,%d" % (x + dx, y)] = c
                            out.append(("blk[%d-%d]x[%d-%d]%+d" % (a, b, ya, yb, dx), p))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug"); ap.add_argument("man"); ap.add_argument("out")
    ap.add_argument("--rounds", type=int, default=12)
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--maxh", type=int, default=4)
    ap.add_argument("--maxw", type=int, default=12)
    ap.add_argument("--maxdx", type=int, default=4)
    ap.add_argument("--pub-cap", type=int, default=0)
    ap.add_argument("--vertical", action="store_true",
                    help="also propose vertical (row-range) shifts")
    ap.add_argument("--fast-search", action="store_true",
                    help="skip stress during search; validate the finalist separately")
    a = ap.parse_args()

    gate = sw_gradelib.Gate(a.slug, a.pub_cap or None)
    print("slug %s  public %d  stress %d" % (a.slug, len(gate.pub), len(gate.stress)),
          flush=True)

    def grade(rows):
        fd, tmp = tempfile.mkstemp(suffix=".man")
        os.close(fd)
        open(tmp, "w").write(wf.render([list(r) for r in rows]))
        try:
            return gate.score(tmp, with_stress=not a.fast_search)
        finally:
            os.unlink(tmp)

    rows = wf.load_rows(a.man)
    base = grade(rows)
    if base is None:
        print("BASE FAILS ITS OWN GATE — aborting", flush=True)
        return
    print("base %.0f" % base, flush=True)
    best = base
    for it in range(a.rounds):
        g = wf.Grid(rows)
        seen, uniq = set(), []
        cands = props(g, a.maxh, a.maxw, a.maxdx)
        if a.vertical:
            cands += vprops(g, a.maxh, a.maxw, a.maxdx)
        for lab, p in cands:
            k = tuple(sorted(p.items()))
            if k not in seen:
                seen.add(k); uniq.append((lab, p))
        print("round %d: %d unique proposals" % (it, len(uniq)), flush=True)
        good = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs) as ex:
            futs = {}
            for (lab, p) in uniq:
                new = ["".join(r) for r in wf.apply_patch(rows, p)]
                futs[ex.submit(grade, new)] = (lab, new)
            for f in concurrent.futures.as_completed(futs):
                s = f.result()
                if s is not None and s < best - 1e-6:
                    good.append((s, futs[f][0], futs[f][1]))
        if not good:
            print("  none improve", flush=True)
            break
        good.sort(key=lambda t: t[0])
        s, lab, new = good[0]
        print("  accept %s  %.0f -> %.0f" % (lab, best, s), flush=True)
        rows, best = new, s
        open(a.out, "w").write(wf.render([list(r) for r in rows]))
    if best < base - 1e-6:
        open(a.out, "w").write(wf.render([list(r) for r in rows]))
        print("WROTE %s  %.0f -> %.0f  (%.2f%%)"
              % (a.out, base, best, 100 * (base - best) / base), flush=True)
    else:
        print("no improvement", flush=True)


if __name__ == "__main__":
    main()
