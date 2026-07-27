#!/usr/bin/env python3
"""Derive the satellite floorplan FROM the port columns, then search only bands.

The 19 floor offsets are not independent knobs: each component has exactly one
x that makes its feeder run zero-length, and a zero-length feeder is a run that
cannot cross anything.  Searching those offsets as free integers is what left
every walk stuck at 5-9 structural faults -- the component and its port have to
move together, and a random walk almost never moves them together.

So: pin every ``*_off`` to its port, and search only the horizontal BANDS (which
row each feeder uses) plus the queue serpentine.  That is 12 knobs instead of
19, and every point in the space already has short feeders.

    cd s4 && python3 scratchpad/pf_derive.py --ports '{...}' --iters 8000
"""
import argparse
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
FORK = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(FORK, "tools"))
sys.path.insert(0, os.path.join(FORK, "solutions", "pathfinder"))
sys.path.insert(0, HERE)

import pf_joint as J  # noqa: E402
import stateflow  # noqa: E402

# offsets that follow their port, and by how much (measured from the pipe
# endpoints stateflow.build_program draws):
#   scratch: sp lands on scratch_x+3, rp leaves from scratch_x+4
#   scalar : sc lands on the RAM command at scalar_x+3
#   cell   : cc lands on the packed proxy command at (cell_x-20)+3
#   display: sa descends onto display_x+8
#   queue  : qs drops straight onto the queue room at queue_x+2
DERIVED = {
    "scratch_off": ("sp", -3),
    "scalar_off": ("sc", -3),
    "cell_off": ("cc", 17),
    "display_off": ("sa", -8),
    "queue_off": ("qs", -2),
}
BAND_KEYS = ["ctop", "scratch_row", "ri_row", "cc_band", "cr_band", "sd_band",
             "sa_band", "ss_band", "queue_row", "display_row", "queue_rows",
             "queue_right_off", "queue_left", "queue_tail"]
BAND_BASE = dict(ctop=5, scratch_row=12, ri_row=12, cc_band=1, cr_band=3,
                 sd_band=-4, sa_band=-3, ss_band=20, queue_row=6,
                 display_row=60, queue_rows=1, queue_right_off=300,
                 queue_left=280, queue_tail=266)


def floor_for(ports, bands):
    f = dict(bands)
    for key, (port, delta) in DERIVED.items():
        f[key] = ports[port] + delta
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ports", required=True)
    ap.add_argument("--iters", type=int, default=8000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--restarts", type=int, default=4)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    ports = {n: stateflow.DEFAULT_PORTS[n][0] for n in stateflow.DEFAULT_PORTS}
    ports.update(json.loads(args.ports))
    rnd = random.Random(args.seed)
    best = None
    t0 = time.time()
    for rs in range(args.restarts):
        bands = dict(BAND_BASE) if best is None else dict(best[1])
        if rs and best is None:
            for k in BAND_KEYS:
                bands[k] = BAND_BASE[k] + rnd.randint(-6, 6)
        cur = J.evaluate(ports, floor_for(ports, bands))
        if cur is None:
            continue
        for it in range(args.iters):
            cand = dict(bands)
            for _ in range(rnd.choice([1, 1, 2, 3])):
                k = rnd.choice(BAND_KEYS)
                cand[k] = cand[k] + rnd.choice([-16, -8, -4, -2, -1,
                                                1, 2, 4, 8, 16])
            got = J.evaluate(ports, floor_for(ports, cand))
            if got is None:
                continue
            if J.key(got) <= J.key(cur):
                bands, cur = cand, got
                if got[0] == 0 and (best is None or J.key(got) < J.key(best[0])):
                    best = (got, dict(cand))
                    print(f"  [{rs}:{it}] CLEAN box {got[1]:,} "
                          f"foot {got[3]}x{got[4]} ctrl {got[5]}x{got[6]}",
                          flush=True)
                    if args.out:
                        json.dump({"ports": ports,
                                   "floor": floor_for(ports, cand)},
                                  open(args.out, "w"), indent=1)
            if it % 2000 == 0:
                print(f"  [{rs}:{it}] cur {J.key(cur)} ({time.time()-t0:.0f}s)",
                      flush=True)
    if best is None:
        print("no clean configuration found")
        return
    got, bands = best
    print(f"\nBEST box {got[1]:,} foot {got[3]}x{got[4]} ctrl {got[5]}x{got[6]}")
    floor = floor_for(ports, bands)
    print("ports =", json.dumps(ports))
    print("floor =", json.dumps(floor))
    if args.out:
        json.dump({"ports": ports, "floor": floor}, open(args.out, "w"),
                  indent=1)


if __name__ == "__main__":
    main()
