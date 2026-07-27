#!/usr/bin/env python3
"""Slide the queue block west on dense-f's floorplan.

With the v6 op stream the controller is 210 rows, so the footprint is 282x267:
the box is now WIDTH-bound, and x 219..266 is 48 columns holding only the ss
port and the queue's return column.  Moving the queue west is therefore worth
~10% of the box outright.

  cd s4 && python3 scratchpad/pf_qshift.py 0 12 24 36 44
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
                                   "dense-f.json")))
QPORTS = ("qs", "qr")
QFLOOR = ("queue_off", "queue_left", "queue_tail", "queue_right_off")


def shifted(delta):
    blob = {"ports": dict(BASE["ports"]), "floor": dict(BASE["floor"])}
    for k in QPORTS:
        blob["ports"][k] -= delta
    for k in QFLOOR:
        blob["floor"][k] -= delta
    return blob


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        d = int(arg)
        blob = shifted(d)
        info, problem = C.check(blob, out=f"/tmp/pf_q{d}.man")
        head = f"queue -{d:3d}: "
        if info:
            head += (f"foot {info[0]}x{info[1]} box {info[2]:,} "
                     f"ctrl {info[3]}x{info[4]}  ")
        print(head + ("OK" if problem is None else problem[:110]), flush=True)
        if problem is None:
            json.dump(blob, open(f"/tmp/pf_q{d}.json", "w"), indent=1)
