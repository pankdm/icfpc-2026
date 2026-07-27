#!/usr/bin/env python3
"""Sweep the RAM belt counts on dense-e's config: footprint + real ticks.

  cd s4 && python3 scratchpad/pf_belts.py 9,4 9,8 6,4 ...
Each argument is `cell_belts,scalar_belts`.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FORK = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(FORK, "tools"))
sys.path.insert(0, os.path.join(FORK, "solutions", "pathfinder"))

import build_rail  # noqa: E402
import manlint  # noqa: E402
import railflow  # noqa: E402
import stateflow  # noqa: E402

CFG = json.load(open(os.path.join(FORK, "solutions", "pathfinder",
                                  "dense-e.json")))
CASE = "there and back again"


def run(cell_belts, scalar_belts, ports=None, floor=None, out=None):
    ports = ports or CFG["ports"]
    shape = dict(floor or CFG["floor"])
    qrows = shape.pop("queue_rows", 1)
    qright = shape.pop("queue_right_off", 300)
    spec = {n: (ports[n], stateflow.DEFAULT_PORTS[n][1]) for n in ports}
    try:
        program, layout = build_rail.build(
            belts=cell_belts, scalar_belts=scalar_belts, verify=False,
            ports=spec, floor=shape, queue_rows=qrows,
            queue_right_off=qright)
    except Exception as exc:
        return f"build: {type(exc).__name__}: {exc}"
    w, h, box = program.footprint()
    head = f"cb={cell_belts} sb={scalar_belts} {w}x{h} box {box:,}"
    fault = manlint.check(program)
    if fault:
        return head + f"  lint: {fault}"
    try:
        railflow.verify_bindings(program, layout)
    except Exception as exc:
        return head + f"  bindings: {exc}"
    path = out or f"/tmp/pf_cb{cell_belts}_sb{scalar_belts}.man"
    program.save(path)
    got = subprocess.run(
        ["node", os.path.join(FORK, "sim", "rust_case.js"), "pathfinder",
         path, CASE], capture_output=True, text=True, cwd=FORK, timeout=600)
    try:
        res = json.loads(got.stdout.strip().splitlines()[-1])
    except Exception:
        return head + f"  smoke: {got.stdout[:150]}{got.stderr[:150]}"
    if res.get("status") != "pass":
        return head + f"  smoke {res.get('status')} {str(res)[:120]}"
    t = res["settleTick"]
    return (head + f"  tick {t:,} boxtick {box * t / 1e9:.2f}G  {path}")


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        cb, sb = (int(v) for v in arg.split(","))
        print(run(cb, sb), flush=True)
