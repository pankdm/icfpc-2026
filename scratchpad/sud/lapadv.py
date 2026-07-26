#!/usr/bin/env python3
"""Scan LAP against the adversarial case the public suite misses:
a box-constraint duplicate carried on lane 2 (the LAST mask an addressing room
sends) landing at round 2, while the fork chain is still birthing men."""
import subprocess, sys, json
BUILDER = "build_lanes5.py"
TC = 32
SOL = "/Users/visenbaev/icfpc26/.claude/worktrees/agent-a6899275a3d404a4a/solutions/sudoku-validity"
CASES = {
    "lane2-box-dup@2":  [(6, 3, 5), (7, 4, 5)],
    "lane2-box-dup@2b": [(6, 6, 9), (8, 7, 9)],
    "lane2-row-dup@2":  [(7, 0, 1), (7, 8, 1)],
    "lane1-box-dup@2":  [(0, 0, 1), (1, 1, 1)],
}
def rounds(cells):
    rows, cols, box = set(), set(), set()
    out = []
    for (r, c, v) in cells:
        b = 3 * (r // 3) + (c // 3)
        bad = (r, v) in rows or (c, v) in cols or (b, v) in box
        out.append({"in": [str(r), str(c), str(v)], "out": ["0" if bad else "1"]})
        if bad: break
        rows.add((r, v)); cols.add((c, v)); box.add((b, v))
    return out

for left in range(int(sys.argv[1]), int(sys.argv[2]) + 1):
    subprocess.run([sys.executable, f"{SOL}/{BUILDER}", str(left), "probe.man"],
                   capture_output=True)
    res = []
    for name, cells in CASES.items():
        o = subprocess.run(["node", "sim/case.js", f"{SOL}/probe.man", json.dumps(rounds(cells))],
                           cwd="/Users/visenbaev/icfpc26", capture_output=True, text=True)
        j = json.loads(o.stdout.strip().splitlines()[-1])
        res.append(f"{name}={j.get('status')}")
    print(f"depth={left:2d} LAP={62+2*left:3d} " + "  ".join(res))
