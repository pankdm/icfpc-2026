#!/usr/bin/env python3
"""Isolate the tick effect of scalar_belts: push the display down far enough
that the sd feeder clears the taller scalar RAM, then measure real ticks.

Box is deliberately sacrificed here -- the question is only whether halving the
scalar RAM's block size buys back the 386k ticks of rr stall.

  cd s4 && python3 scratchpad/pf_sb.py 4 6 8
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pf_belts as P  # noqa: E402

EAST_PORTS = ("sd", "sa", "cc", "cr", "ss", "qs", "qr")
EAST_FLOOR = ("cell_off", "display_off", "queue_off", "queue_left",
              "queue_tail", "queue_right_off")

if __name__ == "__main__":
    for sb in (int(v) for v in sys.argv[1:]):
        ports = dict(P.CFG["ports"])
        floor = dict(P.CFG["floor"])
        delta = max(0, 4 * (sb - 4))          # scalar RAM grows 4 cols per belt
        for k in EAST_PORTS:
            ports[k] += delta
        for k in EAST_FLOOR:
            floor[k] += delta
        floor["display_row"] = max(37, 4 * sb + 16 + 6)  # clear the scalar RAM
        print(P.run(9, sb, ports, floor, out=f"/tmp/pf_sb{sb}.man"), flush=True)
