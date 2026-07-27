#!/usr/bin/env python3
"""Sweep plotter swar geometry knobs.  Builds in the pristine worktree /tmp/plwt
(the live tree has a concurrent agent mid-edit on swar_setup.py) and grades with
the rust engine from the real repo root."""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
WT = "/tmp/plwt/solutions/plotter"
BUILD = os.path.join(WT, "swar_build.py")
GRADE = os.path.join(ROOT, "tools", "grade_fast.py")


def sync():
    subprocess.run(["cp", os.path.join(ROOT, "solutions", "plotter",
                                       "swar_build.py"), WT], check=True)


def run(gap=3, swap=2, spacer=1):
    tag = f"g{gap}s{swap}p{spacer}"
    out = f"/tmp/sw_{tag}.man"
    b = subprocess.run([sys.executable, BUILD, "--gap", str(gap),
                        "--swap-rows", str(swap), "--spacer", str(spacer),
                        "--out", out], capture_output=True, text=True, cwd=WT)
    if b.returncode != 0 or not os.path.exists(out):
        tail = (b.stderr.strip().splitlines() or ["?"])[-1]
        return f"{tag}  BUILD FAIL: {tail[:100]}"
    g = subprocess.run([sys.executable, GRADE, "plotter", out],
                       capture_output=True, text=True, cwd=ROOT)
    try:
        d = json.loads(g.stdout.strip().splitlines()[-1])
    except Exception:
        return f"{tag}  GRADE FAIL: {(g.stdout + g.stderr).strip()[-120:]}"
    fp = d["footprint"]
    bad = sorted({r.get("reason", "?") for r in d["results"]
                  if r["status"] != "pass"})
    return (f"{tag}  {fp['w']}x{fp['h']} box={fp['box']:5d} "
            f"pass={d['passed']}/{d['total']} score={d['score']} {' '.join(bad)}")


if __name__ == "__main__":
    pass  # worktree copy is authoritative; live tree has a concurrent editor
    for args in [dict(spacer=1), dict(spacer=0), dict(spacer=0, swap=1),
                 dict(spacer=0, gap=2)]:
        print(run(**args), flush=True)
