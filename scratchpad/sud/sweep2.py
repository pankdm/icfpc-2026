"""Build+grade a grid of agg2 parameter sets; report box, avgTicks, period, score."""
import itertools, json, os, subprocess, sys, tempfile

ROOT = "/Users/visenbaev/icfpc26/.claude/worktrees/sud-agg"
BUILD = os.path.join(ROOT, "solutions/sudoku-validity/build_agg2.py")
OUT = os.path.join(ROOT, "solutions/sudoku-validity")

grid = []
for dw, dh in [(23, 3), (13, 3), (15, 3), (11, 3), (8, 5)]:
    for rh in [5, 7]:
        for aw, ah in [(9, 5), (14, 3)]:
            grid.append(dict(dw=dw, dh=dh, rh=rh, aw=aw, ah=ah))

for g in grid:
    name = "sw_%s.man" % "_".join(str(v) for v in g.values())
    cmd = [sys.executable, BUILD, "-o", name]
    for k, v in g.items():
        cmd += ["--" + k, str(v)]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        print(g, "BUILD FAIL", r.stderr.strip().splitlines()[-1][:110])
        continue
    path = os.path.join(OUT, name)
    q = subprocess.run([sys.executable, os.path.join(ROOT, "tools/grade_fast.py"),
                        "sudoku-validity", path], capture_output=True, text=True, cwd=ROOT)
    try:
        d = json.loads(q.stdout)
    except Exception:
        print(g, "GRADE FAIL", (q.stdout + q.stderr)[:160])
        os.remove(path)
        continue
    fp = d["footprint"]
    per = max(x["settleTick"] for x in d["results"]) / 81.0
    print("%-52s %2dx%-2d box %4d  ticks %7.1f  period %5.2f  score %10.0f  %d/%d"
          % (g, fp["w"], fp["h"], fp["box"], d["avgTicks"], per,
             d["score"], d["passed"], d["total"]))
    os.remove(path)
