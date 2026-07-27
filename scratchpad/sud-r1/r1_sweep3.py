#!/usr/bin/env python3
"""One build per (DW, slack) using r1_build's auto-lap; multiprocess.
Results -> r1_sweep3.txt, short table printed."""
import os, sys, json, subprocess
ROOT = "/Users/visenbaev/icfpc26/.claude/worktrees/sud-agg"
SOL = ROOT + "/solutions/sudoku-validity"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, SOL); sys.path.insert(0, ROOT + "/tools")

def run(j):
    import r1_build as B
    dw, slack, rw, bw = j
    tag = "%d_%d_%d_%d" % (dw, slack, rw, bw)
    f = "/tmp/r1s3_%s.man" % tag
    try:
        p, ck = B.build(DW=dw, RW=rw, BW=bw, timer_lap=0, lap_slack=slack)
        B.check(ck)
        p.save(f)
    except Exception as e:
        return (j, "buildfail", str(e)[:60])
    w, h, box = p.footprint()
    r = subprocess.run(["python3", ROOT + "/tools/grade_fast.py", "sudoku-validity", f],
                       capture_output=True, text=True, cwd=ROOT)
    try:
        g = json.loads(r.stdout)
    except Exception:
        return (j, "gradefail", (w, h, box), ck["lap"])
    return (j, "%d/%d" % (g["passed"], g["total"]), (w, h, box),
            g.get("avgTicks"), g.get("score") or 9e18, ck["lap"], ck["decide"],
            ck["maxloop"], f)

if __name__ == "__main__":
    import multiprocessing as mp
    jobs = [(dw, s, 8, 9) for dw in range(13, 24) for s in (-4, -2, 0, 1, 2, 3)]
    with mp.Pool(8) as pool:
        res = pool.map(run, jobs)
    with open(os.path.join(HERE, "r1_sweep3.txt"), "w") as fh:
        for r in res:
            fh.write(repr(r) + "\n")
    ok = [r for r in res if r[1] == "6/6"]
    ok.sort(key=lambda r: r[4])
    print("passing", len(ok), "of", len(res))
    for r in ok[:12]:
        print(r[0], r[2], "t", round(r[3], 1), "score", round(r[4]), "lap", r[5],
              "dec", r[6], "ml", r[7])
