#!/usr/bin/env python3
"""Sweep DISX -- the display's top-wall row -- which push9-cfg.json never sets.

Measured why it matters: snake is round-paced.  interp/src/lib.rs releases round
R+1's input only once round R has been judged, and the controller's head read
`r` at (37,10) fires exactly once per round while sitting blocked 18..49 ticks
per round.  So the binding path is controller -> driver -> DISPLAY, not the
controller's own walk, and the driver's longest display pipe is
(45,12)->(46,33) = ~22 cells of pure latency on that path.  DIS_Y = DRV_Y + 10
by default and no champion config has ever moved it.

  python3 snake3_disx.py
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

CFG = json.load(open(os.path.join(HERE, "push9-cfg.json")))
import build_fold8 as B  # noqa: E402


def run(tag, **over):
    kw = dict(CFG, **over)
    out = os.path.join("/tmp", f"snake3_{tag}.man")
    try:
        prog, cap, nrows = B.fit(save_to=out, **kw)
    except Exception as e:
        return f"{tag:12s} BUILD FAIL {type(e).__name__} {str(e)[:70]}", None
    g = subprocess.run([sys.executable, os.path.join(REPO, "tools", "grade_fast.py"),
                        "snake", out], capture_output=True, text=True)
    try:
        d = json.loads(g.stdout.strip().splitlines()[-1])
    except Exception:
        return f"{tag:12s} GRADE FAIL", None
    if d["passed"] != d["total"] or d.get("avgTicks") is None:
        return f"{tag:12s} FAIL {d['passed']}/{d['total']}", None
    w, h = prog.footprint()[0], prog.footprint()[1]
    return (f"{tag:12s} {w}x{h} box {d['footprint']['box']:5d} "
            f"ticks {d['avgTicks']:8.1f} score {d['score']:12.0f}",
            (d["score"], out, kw))


best = None
CASES = [("baseline", {})]
# Display ABOVE the driver: DISX is an ABSOLUTE row, so the two rooms can be
# swapped without touching the emitter.  The long display pipe reaches the
# display's BOTTOM wall, so putting that wall next to the driver is what
# shortens the round-pacing path.
for dy in (2, 3, 4, 5, 6):
    for drv in (20, 21, 22, 23, 24, 25, 26):
        CASES.append((f"D{dy}/V{drv}", dict(DISX=dy, DRVX=drv)))
for line, res in [run(t, **k) for t, k in CASES]:
    print(line, flush=True)
    if res and (best is None or res[0] < best[0]):
        best = res
if best:
    print("BEST", f"{best[0]:.0f}", best[1])
    json.dump(best[2], open(os.path.join(HERE, "snake3-best-cfg.json"), "w"), indent=1)
