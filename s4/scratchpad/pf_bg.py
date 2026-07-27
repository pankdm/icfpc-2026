#!/usr/bin/env python3
"""Build one pathfinder op-stream variant on a saved floorplan, then grade it.

  cd s4 && python3 scratchpad/pf_bg.py build_rail6 dense-f /tmp/pf_v6.man [--grade]
"""
import importlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FORK = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(FORK, "tools"))
sys.path.insert(0, os.path.join(FORK, "solutions", "pathfinder"))

import manlint  # noqa: E402
import railflow  # noqa: E402
import stateflow  # noqa: E402


def main():
    builder, cfg_name, out = sys.argv[1], sys.argv[2], sys.argv[3]
    mod = importlib.import_module(builder)
    cfg = json.load(open(os.path.join(
        FORK, "solutions", "pathfinder", f"{cfg_name}.json")))
    floor = dict(cfg["floor"])
    qrows = floor.pop("queue_rows", 1)
    qright = floor.pop("queue_right_off", 300)
    spec = {n: (cfg["ports"][n], stateflow.DEFAULT_PORTS[n][1])
            for n in cfg["ports"]}
    kw = {}
    for flag, name in (("--belts", "belts"), ("--sbelts", "scalar_belts")):
        if flag in sys.argv:
            kw[name] = int(sys.argv[sys.argv.index(flag) + 1])
    program, layout = mod.build(verify=False, ports=spec, floor=floor,
                                queue_rows=qrows, queue_right_off=qright,
                                **kw)
    w, h, box = program.footprint()
    print(f"{w}x{h} box {box:,} ctrl {layout['width']}x{layout['height']} "
          f"rail {layout['ncorr']}", flush=True)
    fault = manlint.check(program)
    if fault:
        sys.exit(f"lint: {fault}")
    railflow.verify_bindings(program, layout)
    program.save(out)
    if "--grade" in sys.argv:
        got = subprocess.run(
            ["python3", os.path.join(FORK, "tools", "grade_fast.py"),
             "pathfinder", out], capture_output=True, text=True, cwd=FORK)
        d = json.loads(got.stdout)
        print(f"{d['passed']}/{d['total']}  box {d['footprint']['box']:,}  "
              f"avgTicks {d['avgTicks']:,.0f}  score {d['score']:,.0f}")


main()
