#!/usr/bin/env python3
"""rowmerge.py <in.man> <out.man> — grade-gated adjacent-row merge (height -1 per hit).

Two neighbouring interior rows whose glyph COLUMNS are disjoint can be written onto one
row; deleting the vacated row shifts every wall, pipe and satellite room below it up as a
block, so the box loses a row.  Whether the man's walk survives is not something static
analysis settles here, so every merge is graded.
"""
import sys, os, json, subprocess, tempfile
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
    return (d["score"], d["footprint"]) if d["passed"] == d["total"] else None


def main():
    src, out = sys.argv[1], sys.argv[2]
    rows = wf.load_rows(src)
    base = grade(rows)
    print("base", base)
    improved = True
    while improved:
        improved = False
        g = wf.Grid(rows)
        (x0, y0), (x1, y1) = g.rooms[0]["min"], g.rooms[0]["max"]
        cols = {y: {x for x in range(x0 + 1, x1) if g.at(x, y) != " "}
                for y in range(y0 + 1, y1)}
        for y in range(y0 + 1, y1 - 1):
            for keep, drop in ((y, y + 1), (y + 1, y)):
                if cols[y] & cols[y + 1]:
                    continue
                w = max(len(r) for r in rows)
                merged = list(rows[keep].ljust(w))
                for x in cols[drop]:
                    merged[x] = rows[drop][x]
                new = [rows[i] for i in range(len(rows)) if i != drop]
                new[keep - (1 if drop < keep else 0)] = "".join(merged)
                r = grade(new)
                if r and r[0] < base[0]:
                    print(f"  merged rows {y},{y+1} onto {keep} -> {r}")
                    rows, base, improved = new, r, True
                    open(out, "w").write(wf.render([list(x) for x in rows]))
                    break
                elif r:
                    print(f"  rows {y},{y+1} keep {keep}: passes but {r[0]:.0f} >= {base[0]:.0f}")
            if improved:
                break
    print("done", base)


main()
