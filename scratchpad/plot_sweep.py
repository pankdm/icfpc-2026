#!/usr/bin/env python3
"""Sweep the plotter build's tick knobs.  Every one of these is a pipe whose
cells the ROUND SENTINEL walks, or a loop whose length is CTRL's fetch latency,
so each cell is ~1 tick per round.  They were set by derivation; this measures
them instead (which is how ZIG turned out to be two cells too long)."""
import itertools
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(REPO, "solutions", "plotter"))
import swar_build as B  # noqa: E402

grid = {
    "LOOP": [int(v) for v in (sys.argv[1] if len(sys.argv) > 1 else "3,2,1").split(",")],
    "SWCOL": [int(v) for v in (sys.argv[2] if len(sys.argv) > 2 else "3,2,1").split(",")],
    "ZIG": [int(v) for v in (sys.argv[3] if len(sys.argv) > 3 else "7").split(",")],
    "GAP": [int(v) for v in (sys.argv[4] if len(sys.argv) > 4 else "3").split(",")],
    "SWAP_ROWS": [int(v) for v in (sys.argv[5] if len(sys.argv) > 5 else "2").split(",")],
}
best = None
for combo in itertools.product(*grid.values()):
    for k, v in zip(grid, combo):
        setattr(B, k, v)
    tag = " ".join(f"{k}={v}" for k, v in zip(grid, combo))
    try:
        p, _ = B.build()
        p.save("/tmp/plot_sweep.man")
    except Exception as e:
        print(f"{tag:28s} BUILD {str(e)[:60]}")
        continue
    r = subprocess.run([sys.executable, os.path.join(REPO, "tools", "grade_fast.py"),
                        "plotter", "/tmp/plot_sweep.man", "--cap", "30000"],
                       capture_output=True, text=True, timeout=600)
    try:
        v = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        print(f"{tag:28s} GRADE-ERR")
        continue
    ok = v["passed"] == v["total"]
    sc = v["score"] if ok else None
    print(f"{tag:28s} {v['passed']}/{v['total']}  box {v['footprint']['box']}"
          f"  avgTicks {v['avgTicks']}  score {sc}")
    if ok and (best is None or sc < best[0]):
        best = (sc, tag)
print("BEST", best)
