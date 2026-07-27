#!/usr/bin/env python3
"""Build a {ports,floor} json, report footprint and the first stage that fails.

  cd s4 && python3 scratchpad/pf_check.py /tmp/pf_hand.json [--smoke]
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


def check(blob, smoke=False, out="/tmp/pf_check.man", quiet=False):
    ports, floor = blob["ports"], dict(blob["floor"])
    qrows = floor.pop("queue_rows", 1)
    qright = floor.pop("queue_right_off", 300)
    spec = {n: (ports[n], stateflow.DEFAULT_PORTS[n][1]) for n in ports}
    try:
        program, layout = build_rail.build(
            verify=False, ports=spec, floor=floor,
            queue_rows=qrows, queue_right_off=qright)
    except Exception as exc:
        return None, f"build: {type(exc).__name__}: {exc}"
    w, h, box = program.footprint()
    info = (w, h, box, layout["width"], layout["height"])
    bad = manlint.bad_overwrites(program)
    if bad:
        return info, f"{len(bad)} collisions, first {bad[:3]}"
    lf = manlint.literal_faults(program.render().split("\n"))
    if lf:
        return info, f"literal faults {lf[:3]}"
    qr = layout["ports"]["qr"]
    queue = [rec[2] for rec in program.pipes if rec[1] == qr]
    if not queue or min(queue) < 40:
        return info, f"queue capacity {queue and min(queue)}"
    try:
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            railflow.verify_bindings(program, layout)
    except Exception as exc:
        return info, f"bindings: {exc}"
    program.save(out)
    if smoke:
        got = subprocess.run(
            ["node", os.path.join(FORK, "sim", "rust_case.js"), "pathfinder",
             out, "there and back again"],
            capture_output=True, text=True, cwd=FORK, timeout=400)
        if '"status":"pass"' not in got.stdout:
            return info, f"smoke: {got.stdout.strip()[:200]}"
        tick = json.loads(got.stdout.strip().splitlines()[-1])["settleTick"]
        return info + (tick,), None
    return info, None


if __name__ == "__main__":
    blob = json.load(open(sys.argv[1]))
    info, problem = check(blob, smoke="--smoke" in sys.argv)
    if info:
        print(f"foot {info[0]}x{info[1]} box {info[2]:,} "
              f"ctrl {info[3]}x{info[4]}"
              + (f" tick {info[5]:,} boxtick {info[2]*info[5]/1e9:.2f}G"
                 if len(info) > 5 else ""))
    print("OK" if problem is None else problem)
