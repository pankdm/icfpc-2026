#!/usr/bin/env python3
"""rowkill.py — grade-gated row deletion: push each glyph of a row onto the row above OR below.

`walkfold squash` can only delete a row that is already empty and `rowmerge` only folds a
whole row onto ONE neighbour.  Several rows here are half-foldable: some glyphs have a free
cell above, the rest have one below.  Enumerate every up/down assignment of a row's glyphs,
delete the row, and grade.  Each hit is one row of height, i.e. ~3% of the box.
"""
import sys, os, json, subprocess, tempfile, itertools, concurrent.futures
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


def main():
    src, out = sys.argv[1], sys.argv[2]
    rows = wf.load_rows(src)
    base = grade(rows)
    print(f"base {base:.0f}", flush=True)
    again = True
    while again:
        again = False
        g = wf.Grid(rows)
        (x0, y0), (x1, y1) = g.rooms[0]["min"], g.rooms[0]["max"]
        cands = []
        for y in range(y0 + 2, y1 - 1):
            gl = [(x, g.at(x, y)) for x in range(x0 + 1, x1) if g.at(x, y) != " "]
            if not gl or len(gl) > 8:
                continue
            opts = []
            for (x, ch) in gl:
                o = [d for d in (-1, 1) if g.at(x, y + d) == " "]
                if not o:
                    opts = None
                    break
                opts.append(o)
            if opts is None:
                continue
            combos = list(itertools.product(*opts))
            if len(combos) > 64:
                combos = combos[:64]
            for combo in combos:
                patch = {}
                clash = False
                for (x, ch), d in zip(gl, combo):
                    k = f"{x},{y + d}"
                    if k in patch:
                        clash = True
                    patch[k] = ch
                if clash:
                    continue
                new = [list(r.ljust(x1 + 1)) for r in rows]
                for k, v in patch.items():
                    a, b = (int(t) for t in k.split(","))
                    new[b][a] = v
                new = ["".join(r) for i, r in enumerate(new) if i != y]
                cands.append((f"kill row {y} dirs {combo}", new))
        print(f"  {len(cands)} deletion candidates", flush=True)
        best = None
        with concurrent.futures.ThreadPoolExecutor(max_workers=9) as ex:
            futs = {ex.submit(grade, n): (lab, n) for lab, n in cands}
            for f in concurrent.futures.as_completed(futs):
                s = f.result()
                if s is not None and s < base - 1e-6 and (best is None or s < best[0]):
                    best = (s, futs[f][0], futs[f][1])
        if best:
            base, rows, again = best[0], best[2], True
            print(f"  {best[1]} -> {base:.0f}", flush=True)
            open(out, "w").write(wf.render([list(r) for r in rows]))
    print(f"done {base:.0f}", flush=True)


main()
