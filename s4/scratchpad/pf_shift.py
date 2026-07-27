#!/usr/bin/env python3
"""Shift everything east of the scalar RAM by D columns, sweep belt counts.

  cd s4 && python3 scratchpad/pf_shift.py <D> <cell_belts> <scalar_belts> ...
Each triple is one candidate.
"""
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pf_belts as P  # noqa: E402

EAST_PORTS = ("sd", "sa", "cc", "cr", "ss", "qs", "qr")
EAST_FLOOR = ("cell_off", "display_off", "queue_off", "queue_left",
              "queue_tail", "queue_right_off")


def cfg(delta):
    ports = dict(P.CFG["ports"])
    floor = dict(P.CFG["floor"])
    for k in EAST_PORTS:
        ports[k] += delta
    for k in EAST_FLOOR:
        floor[k] += delta
    return ports, floor


if __name__ == "__main__":
    args = sys.argv[1:]
    for i in range(0, len(args), 3):
        d, cb, sb = (int(v) for v in args[i:i + 3])
        ports, floor = cfg(d)
        print(f"D={d} ", P.run(cb, sb, ports, floor,
                               out=f"/tmp/pf_d{d}_{cb}_{sb}.man"), flush=True)
