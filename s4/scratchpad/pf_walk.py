#!/usr/bin/env python3
"""Anneal the 12 port columns with the floor DERIVED (pf_floor) and the box
measured by the REAL builder.

The fast row model under-predicts by 8-17 rows (rail allocation adds padding
rows it does not simulate) and the satellite band is 59, not 55, so a search
that trusts it ranks candidates wrongly.  Deriving the floor makes the search
12-dimensional instead of 31, which is what makes a real-build objective
affordable (~0.15 s/eval).

  cd s4 && python3 scratchpad/pf_walk.py --start /tmp/pf_c601.json --iters 400
"""
import argparse
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pf_bandsearch as B  # noqa: E402
import pf_check as C  # noqa: E402
import pf_floor as F  # noqa: E402

PORTS = list(B.BASE)


def cost(ports):
    if len(set(ports.values())) != len(ports):
        return None
    if not B.placeable(ports):
        return None
    try:
        floor = F.derive(ports)
    except ValueError:
        return None
    info, problem = C.check({"ports": ports, "floor": floor},
                            out="/tmp/pf_walk.man")
    if problem or info is None:
        return None
    return info[2], info[0], info[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--iters", type=int, default=400)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default="/tmp/pf_walk.json")
    args = ap.parse_args()
    ports = json.load(open(args.start))["ports"]
    rnd = random.Random(args.seed)
    cur = cost(ports)
    assert cur is not None, "start is infeasible"
    print("start box", f"{cur[0]:,}", cur[1], "x", cur[2], flush=True)
    best = (cur, dict(ports))
    t0 = time.time()
    for it in range(args.iters):
        cand = dict(ports)
        for _ in range(rnd.choice([1, 1, 2])):
            n = rnd.choice(PORTS)
            cand[n] = max(1, cand[n] + rnd.choice(
                [-24, -12, -6, -3, -2, -1, 1, 2, 3, 6, 12, 24]))
        got = cost(cand)
        if got is None:
            continue
        if got <= cur:
            ports, cur = cand, got
            if got[0] < best[0][0]:
                best = (got, dict(cand))
                print(f"  [{it}] box {got[0]:,} {got[1]}x{got[2]} "
                      f"({time.time()-t0:.0f}s)", flush=True)
                json.dump({"ports": cand, "floor": F.derive(cand)},
                          open(args.out, "w"), indent=1)
    print("BEST", f"{best[0][0]:,}", best[0][1], "x", best[0][2])
    print("ports =", json.dumps(best[1]))


main()
