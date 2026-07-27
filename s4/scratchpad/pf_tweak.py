#!/usr/bin/env python3
"""Apply floor/port overrides to a saved config, build, and report.

  cd s4 && python3 scratchpad/pf_tweak.py qshift44 '{"display_row":20}' ...
Each extra argument is one override dict; all are tried independently.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FORK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(FORK, "tools"))

import pf_check as C  # noqa: E402

BASE = json.load(open(os.path.join(FORK, "solutions", "pathfinder",
                                   f"{sys.argv[1]}.json")))

for i, arg in enumerate(sys.argv[2:]):
    over = json.loads(arg)
    blob = {"ports": dict(BASE["ports"]), "floor": dict(BASE["floor"])}
    blob["ports"].update(over.pop("ports", {}))
    blob["floor"].update(over)
    info, problem = C.check(blob, out=f"/tmp/pf_tw{i}.man")
    head = f"{arg[:70]:<70} "
    if info:
        head += f"foot {info[0]}x{info[1]} box {info[2]:,} ctrl {info[3]}x{info[4]}  "
    print(head + ("OK" if problem is None else problem[:90]), flush=True)
    if problem is None:
        json.dump(blob, open(f"/tmp/pf_tw{i}.json", "w"), indent=1)
