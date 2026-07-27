#!/usr/bin/env python3
"""Anneal port columns around a KNOWN-GOOD config, real builder, minimise box.

Unlike pf_floor.derive (which re-pins every component to a zero-length feeder
and so jumps to a different routing topology), this keeps every offset at the
delta it already has in the seed config and slides the (port, component) pairs
together.  The seed therefore stays feasible and the walk explores only the
spacing -- which is what sets the newline count, i.e. the controller rows, i.e.
the box now that the footprint is height-bound.

  cd s4 && python3 scratchpad/pf_anneal2.py v6a --iters 600 --belts 8
"""
import argparse
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
FORK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(FORK, "tools"))
sys.path.insert(0, os.path.join(FORK, "solutions", "pathfinder"))

import build_rail6  # noqa: E402
import manlint  # noqa: E402
import railflow  # noqa: E402
import stateflow  # noqa: E402

# floor key -> the port it must move with
FOLLOWS = {"scratch_off": "sp", "scalar_off": "sc", "cell_off": "cc",
           "display_off": "sa", "queue_off": "qs", "queue_left": "qs",
           "queue_tail": "qs", "queue_right_off": "qs", "sd_via": "sd"}
PORTS = ["ri", "sp", "rp", "sc", "rr", "sd", "sa", "ss", "cc", "cr",
         "qs", "qr"]


def make(seed, ports):
    floor = dict(seed["floor"])
    for key, port in FOLLOWS.items():
        if key in floor:
            floor[key] += ports[port] - seed["ports"][port]
    return {"ports": ports, "floor": floor}


def evaluate(blob, belts, base_dangling):
    floor = dict(blob["floor"])
    q = floor.pop("queue_rows", 1)
    qr = floor.pop("queue_right_off", 300)
    spec = {n: (blob["ports"][n], stateflow.DEFAULT_PORTS[n][1])
            for n in blob["ports"]}
    try:
        program, layout = build_rail6.build(
            belts=belts, verify=False, ports=spec, floor=floor,
            queue_rows=q, queue_right_off=qr)
    except Exception:
        return None
    if manlint.bad_overwrites(program):
        return None
    if manlint.dangling_signature(program) != base_dangling:
        return None
    if manlint.literal_faults(program.render().split("\n")):
        return None
    qrp = layout["ports"]["qr"]
    queue = [rec[2] for rec in program.pipes if rec[1] == qrp]
    if not queue or min(queue) < 40:
        return None
    try:
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            railflow.verify_bindings(program, layout)
    except Exception:
        return None
    w, h, box = program.footprint()
    return box, w + h, w, h, layout["height"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("seed")
    ap.add_argument("--iters", type=int, default=600)
    ap.add_argument("--belts", type=int, default=8)
    ap.add_argument("--seed-rng", type=int, default=1)
    ap.add_argument("--out", default="/tmp/pf_a2.json")
    args = ap.parse_args()
    seed = json.load(open(os.path.join(
        FORK, "solutions", "pathfinder", f"{args.seed}.json")))
    floor = dict(seed["floor"])
    q = floor.pop("queue_rows", 1)
    qr = floor.pop("queue_right_off", 300)
    spec = {n: (seed["ports"][n], stateflow.DEFAULT_PORTS[n][1])
            for n in seed["ports"]}
    program, _ = build_rail6.build(belts=args.belts, verify=False, ports=spec,
                                   floor=floor, queue_rows=q,
                                   queue_right_off=qr)
    base_dangling = manlint.dangling_signature(program)
    ports = dict(seed["ports"])
    cur = evaluate(make(seed, ports), args.belts, base_dangling)
    assert cur is not None, "seed is infeasible"
    print("start box", f"{cur[0]:,}", f"{cur[2]}x{cur[3]}", "ctrl rows",
          cur[4], flush=True)
    best = (cur, dict(ports))
    rnd = random.Random(args.seed_rng)
    t0 = time.time()
    for it in range(args.iters):
        cand = dict(ports)
        for _ in range(rnd.choice([1, 1, 2])):
            n = rnd.choice(PORTS)
            cand[n] = max(1, cand[n] + rnd.choice(
                [-16, -8, -4, -3, -2, -1, 1, 2, 3, 4, 8, 16]))
        if len(set(cand.values())) != len(cand):
            continue
        got = evaluate(make(seed, cand), args.belts, base_dangling)
        if got is None:
            continue
        if got <= cur:
            ports, cur = cand, got
            if got[0] < best[0][0]:
                best = (got, dict(cand))
                print(f"  [{it}] box {got[0]:,} {got[2]}x{got[3]} rows "
                      f"{got[4]} ({time.time()-t0:.0f}s)", flush=True)
                json.dump(make(seed, cand), open(args.out, "w"), indent=1)
    print("BEST", f"{best[0][0]:,}", f"{best[0][2]}x{best[0][3]}",
          "rows", best[0][4])
    print("ports =", json.dumps(best[1]))


main()
