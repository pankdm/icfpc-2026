#!/usr/bin/env python3
"""Compare the dangling-pipe signature of two configs (baseline vs candidate)."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FORK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(FORK, "tools"))
sys.path.insert(0, os.path.join(FORK, "solutions", "pathfinder"))

import build_rail6  # noqa: E402
import manlint  # noqa: E402
import stateflow  # noqa: E402


def build(blob, belts=9):
    floor = dict(blob["floor"])
    q = floor.pop("queue_rows", 1)
    qr = floor.pop("queue_right_off", 300)
    spec = {n: (blob["ports"][n], stateflow.DEFAULT_PORTS[n][1])
            for n in blob["ports"]}
    return build_rail6.build(belts=belts, verify=False, ports=spec,
                             floor=floor, queue_rows=q, queue_right_off=qr)


for path in sys.argv[1:]:
    blob = json.load(open(path)) if path.endswith(".json") else json.load(
        open(os.path.join(FORK, "solutions", "pathfinder", f"{path}.json")))
    program, _ = build(blob)
    print(path, "dangling:", sorted(manlint.dangling_signature(program)))
