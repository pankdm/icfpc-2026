#!/usr/bin/env python3
"""blockshift.py — grade-gated shift of an ISOLATED rectangle of glyphs.

The hot belt-scan loops keep their `X`/`-`/literal block ~8 columns west of the belt band,
so the man glides over the gap twice on every lap.  Sliding that whole block east shortens
each lap.  A candidate block is a column range [a,b] inside a row window whose bounding
columns a-1 and b+1 are blank on every row of the window (so it is not welded to anything
else), shifted by dx with every destination cell blank.

Every candidate is graded; kept only if all 7 public cases pass and the score improves.

usage: blockshift.py <in.man> <out.man> [--rounds N] [--jobs N] [--maxh N] [--maxw N]
"""
import sys, os, json, subprocess, tempfile, argparse, concurrent.futures
REPO = "/Users/visenbaev/icfpc26"
sys.path.insert(0, os.path.join(REPO, "tools"))
os.chdir(REPO)
import walkfold as wf


def grade(rows):
    fd, tmp = tempfile.mkstemp(suffix=".man")
    os.close(fd)
    open(tmp, "w").write(wf.render([list(r) for r in rows]))
    p = subprocess.run(["python3", "tools/grade_fast.py", "gradebook", tmp, "--cap", "60000"],
                       capture_output=True, text=True)
    os.unlink(tmp)
    try:
        d = json.loads(p.stdout)
    except Exception:
        return None
    return d["score"] if d["passed"] == d["total"] else None


def props(g, maxh, maxw, maxdx):
    (x0, y0), (x1, y1) = g.rooms[0]["min"], g.rooms[0]["max"]
    out = []
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
                    cells = [(x, y, g.at(x, y)) for y in ys for x in range(a, b + 1)
                             if g.at(x, y) != " "]
                    if not cells:
                        continue
                    for dx in list(range(1, maxdx + 1)) + list(range(-1, -maxdx - 1, -1)):
                        if not (x0 < a + dx and b + dx < x1):
                            continue
                        if any(g.at(x + dx, y) != " " for y in ys
                               for x in range(a, b + 1) if not (a <= x + dx <= b)):
                            continue
                        p = {f"{x},{y}": " " for x, y, _ in cells}
                        for (x, y, c) in cells:
                            p[f"{x + dx},{y}"] = c
                        out.append((f"blk[{a}-{b}]x[{ya}-{yb}]{dx:+d}", p))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("man"); ap.add_argument("out")
    ap.add_argument("--rounds", type=int, default=30)
    ap.add_argument("--jobs", type=int, default=9)
    ap.add_argument("--maxh", type=int, default=5)
    ap.add_argument("--maxw", type=int, default=14)
    ap.add_argument("--maxdx", type=int, default=5)
    a = ap.parse_args()
    rows = wf.load_rows(a.man)
    base = grade(rows)
    print(f"base {base:.0f}", flush=True)
    for it in range(a.rounds):
        g = wf.Grid(rows)
        ps = props(g, a.maxh, a.maxw, a.maxdx)
        seen, uniq = set(), []
        for lab, p in ps:
            k = tuple(sorted(p.items()))
            if k not in seen:
                seen.add(k); uniq.append((lab, p))
        print(f"round {it}: {len(uniq)} unique proposals", flush=True)
        best = None
        with concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs) as ex:
            futs = {}
            for (lab, p) in uniq:
                new = ["".join(r) for r in wf.apply_patch(rows, p)]
                futs[ex.submit(grade, new)] = (lab, new)
            for f in concurrent.futures.as_completed(futs):
                s = f.result()
                if s is not None and s < base - 1e-6 and (best is None or s < best[0]):
                    best = (s, futs[f][0], futs[f][1])
        if best is None:
            print("  none improve", flush=True)
            break
        base, rows = best[0], best[2]
        print(f"  took {best[1]} -> {base:.0f}", flush=True)
        open(a.out, "w").write(wf.render([list(r) for r in rows]))
    print(f"done -> {a.out} ({base:.0f})", flush=True)


main()
