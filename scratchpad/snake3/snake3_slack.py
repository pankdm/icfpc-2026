#!/usr/bin/env python3
"""Prove (or refute) that snake's period is DISPLAY-CHAIN bound, not controller bound.

interp/src/lib.rs releases round R+1's input only after round R has been judged,
so the controller's head read blocks until the driver has pushed round R's frame.
If that is the binding path, then knobs that only lengthen/shorten the
CONTROLLER's walk move ticks far less per column than knobs on the DRIVER leg.

Builds push9's config with one knob perturbed at a time and grades each.

  python3 snake3_slack.py
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
        return f"{tag:16s} BUILD FAIL {type(e).__name__} {str(e)[:60]}"
    g = subprocess.run([sys.executable, os.path.join(REPO, "tools", "grade_fast.py"),
                        "snake", out], capture_output=True, text=True)
    try:
        d = json.loads(g.stdout.strip().splitlines()[-1])
    except Exception:
        return f"{tag:16s} GRADE FAIL"
    if d.get("avgTicks") is None or d["passed"] != d["total"]:
        return f"{tag:16s} FAIL {d['passed']}/{d['total']}"
    return (f"{tag:16s} {prog.footprint()[0]}x{prog.footprint()[1]} "
            f"box {d['footprint']['box']:5d} pass {d['passed']}/{d['total']} "
            f"ticks {d['avgTicks']:8.1f} score {d['score']:12.0f}")


print(run("baseline"))
# Controller-only travel: the left inset and the state-lane origin move where the
# controller walks; neither is on the driver leg.
for v in (6, 7):
    print(run(f"CXL={v}", CXL=v))
for v in (17, 20):
    print(run(f"ST_X0={v}", ST_X0=v))
# Driver leg: these move the display chain the round pacing waits on.
for v in (4, 6, 7):
    print(run(f"DRVX={v}", DRVX=v))
for v in (47, 51, 53):
    print(run(f"DRV_OUT={v}", DRV_OUT=v))
