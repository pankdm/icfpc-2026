#!/usr/bin/env python3
"""DW x lap sweep on the 6-row-strip / east-INPUT build."""
import os, sys, json, subprocess
ROOT = "/Users/visenbaev/icfpc26/.claude/worktrees/sud-agg"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, ROOT + "/solutions/sudoku-validity")
sys.path.insert(0, ROOT + "/tools")

def run(j):
    import r1_build as B
    dw, lap = j
    f = "/tmp/r1L_%d_%d.man" % (dw, lap)
    try:
        p, ck = B.build(DW=dw, timer_lap=lap)
        B.check(ck)
        p.save(f)
    except Exception as e:
        return (j, "buildfail", str(e)[:50])
    w, h, box = p.footprint()
    r = subprocess.run(["python3", ROOT + "/tools/grade_fast.py", "sudoku-validity", f],
                       capture_output=True, text=True, cwd=ROOT, timeout=600)
    try:
        g = json.loads(r.stdout)
    except Exception:
        return (j, "gradefail", (w, h, box))
    return (j, "%d/%d" % (g["passed"], g["total"]), (w, h, box),
            g.get("avgTicks"), g.get("score") or 9e18, ck["decide"], ck["maxloop"], f)

if __name__ == "__main__":
    import multiprocessing as mp
    jobs = [(dw, lap) for dw in (18, 19, 20, 21, 22) for lap in (38, 40, 42, 44)]
    with mp.Pool(8) as pool:
        res = pool.map(run, jobs)
    ok = [r for r in res if r[1] == "6/6"]
    ok.sort(key=lambda r: r[4])
    print("pass", len(ok), "of", len(res))
    for r in ok[:10]:
        print(r[0], r[2], round(r[3], 1), round(r[4]), "dec", r[5], "ml", r[6], r[7])
