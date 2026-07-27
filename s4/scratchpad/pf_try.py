#!/usr/bin/env python3
"""Try one (ports, floor) config end to end WITHOUT writing a solution file.

Prints footprint / controller / the first stage that rejects it, so a proposal
from the fast geometry model can be triaged in one second instead of a grade.

    cd s4 && python3 scratchpad/pf_try.py --ports '{...}' [--floor '{...}']
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FORK = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(FORK, "tools"))
sys.path.insert(0, os.path.join(FORK, "solutions", "pathfinder"))

import build_rail  # noqa: E402
import manlint  # noqa: E402
import railflow  # noqa: E402
import stateflow  # noqa: E402

BASE_FLOOR = dict(scalar_off=48, cell_off=164, ctop=5, scratch_off=18,
                  scratch_row=12, ri_row=12, display_off=110, cc_band=1,
                  cr_band=3, queue_off=268, queue_row=6, queue_left=280,
                  queue_tail=266, sd_band=-4, sa_band=-3, ss_band=20,
                  queue_rows=1, queue_right_off=300, display_row=60)


def attempt(ports, floor, smoke=True, slug="pathfinder",
            case="there and back again", queue_floor=40):
    shape = dict(floor)
    qrows = shape.pop("queue_rows", 1)
    qright = shape.pop("queue_right_off", 300)
    spec = {n: (ports[n], stateflow.DEFAULT_PORTS[n][1]) for n in ports}
    try:
        program, layout = build_rail.build(
            verify=False, ports=spec, floor=shape,
            queue_rows=qrows, queue_right_off=qright)
    except Exception as exc:
        return None, f"build: {type(exc).__name__}: {exc}"
    w, h, box = program.footprint()
    info = (w, h, box, layout["width"], layout["height"])
    fault = manlint.check(program)
    if fault:
        return info, f"lint: {fault}"
    qr = layout["ports"]["qr"]
    queue = [rec[2] for rec in program.pipes if rec[1] == qr]
    if not queue or min(queue) < queue_floor:
        return info, f"queue capacity {queue and min(queue)}"
    try:
        railflow.verify_bindings(program, layout)
    except Exception as exc:
        return info, f"bindings: {exc}"
    if not smoke:
        return info, None
    fd, path = tempfile.mkstemp(suffix=".man")
    os.close(fd)
    try:
        program.save(path)
        got = subprocess.run(
            ["node", os.path.join(FORK, "sim", "rust_case.js"), slug, path, case],
            capture_output=True, text=True, cwd=FORK, timeout=300)
        if '"status":"pass"' not in got.stdout:
            return info, f"smoke: {got.stdout.strip()[:160]}"
    finally:
        os.unlink(path)
    return info, None


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ports", required=True)
    ap.add_argument("--floor", default=None)
    ap.add_argument("--no-smoke", action="store_true")
    args = ap.parse_args()
    ports = dict({n: stateflow.DEFAULT_PORTS[n][0]
                  for n in stateflow.DEFAULT_PORTS}, **json.loads(args.ports))
    floor = dict(BASE_FLOOR, **(json.loads(args.floor) if args.floor else {}))
    info, problem = attempt(ports, floor, smoke=not args.no_smoke)
    if info:
        print(f"foot {info[0]}x{info[1]} box {info[2]:,} "
              f"controller {info[3]}x{info[4]}")
    print("OK" if problem is None else problem)
