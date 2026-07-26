#!/usr/bin/env python3
"""Joint search over Pathfinder's port columns and satellite floorplan.

Same idea as ``solutions/snake/search_rail.py``: the controller's height is the
number of boustrophedon rows, a row ends whenever the next op's Voronoi band is
behind the cursor, and the bands are set entirely by the port columns.  Pathfinder
additionally carries a FIFO queue whose *return pipe length is its capacity*, so
any proposal that shortens it below ``--queue-floor`` cells is rejected outright.

  python3 solutions/pathfinder/search_rail.py --iters 3000
"""

import argparse
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))
sys.path.insert(0, HERE)

import build_rail  # noqa: E402
import manlint  # noqa: E402
import stateflow  # noqa: E402

PORTS = ["ri", "sp", "rp", "sc", "rr", "sd", "sa", "ss", "cc", "cr", "qs", "qr"]
FLOOR_KEYS = ["scalar_off", "cell_off", "ctop", "scratch_off", "scratch_row",
              "ri_row", "display_off", "cc_band", "cr_band", "queue_off",
              "queue_row", "queue_left", "queue_tail", "sd_band", "sa_band",
              "ss_band",
              # the queue serpentine's east edge is what pins the whole
              # footprint width; without these two the search cannot reach it
              "queue_rows", "queue_right_off",
              # display_row lifts the display out from under the RAM stack --
              # 60 rows below `bottom` is why this satellite band is 81 rows
              "display_row"]
BASE_PORTS = {n: stateflow.DEFAULT_PORTS[n][0] for n in PORTS}
BASE_FLOOR = dict(scalar_off=48, cell_off=164, ctop=5, scratch_off=18,
                  scratch_row=12, ri_row=12, display_off=110, cc_band=1,
                  cr_band=3, queue_off=268, queue_row=6, queue_left=280,
                  queue_tail=266, sd_band=-4, sa_band=-3, ss_band=20,
                  queue_rows=1, queue_right_off=300, display_row=60)
QUEUE_FLOOR = 40   # measured BFS frontier is <= ~19 items; keep 2x headroom
BASE_DANGLING = None   # set from the baseline build on first evaluate


def evaluate(cols, floor, verify=False, queue_floor=QUEUE_FLOOR):
    if len(set(cols.values())) != len(cols):
        return None
    spec = {n: (cols[n], stateflow.DEFAULT_PORTS[n][1]) for n in PORTS}
    shape = dict(floor)
    qrows = shape.pop("queue_rows", 1)
    qright = shape.pop("queue_right_off", 300)
    if qrows < 1 or qrows > 24:
        return None
    try:
        program, layout = build_rail.build(
            verify=False, ports=spec, floor=shape,
            queue_rows=qrows, queue_right_off=qright)
    except Exception:
        return None
    if manlint.bad_overwrites(program):
        return None
    global BASE_DANGLING
    loose = manlint.dangling_signature(program)
    if BASE_DANGLING is None:
        BASE_DANGLING = loose
    elif loose != BASE_DANGLING:
        return None
    qr = layout["ports"]["qr"]
    queue = [rec[2] for rec in program.pipes if rec[1] == qr]
    if not queue or min(queue) < queue_floor:
        return None
    if manlint.literal_faults(program.render().split("\n")):
        return None
    if verify:
        try:
            build_rail.railflow.verify_bindings(program, layout)
        except Exception:
            return None
    w, h, box = program.footprint()
    return box, w, h, layout["width"], layout["height"], layout["ncorr"]


def search(iters, seed, start=None):
    rnd = random.Random(seed)
    cols = dict(BASE_PORTS) if start is None else dict(start[0])
    floor = dict(BASE_FLOOR) if start is None else dict(start[1])
    cur = evaluate(cols, floor)
    assert cur is not None, "baseline is infeasible"
    best = (cur, dict(cols), dict(floor))
    accepted = 0
    for _ in range(iters):
        cand_cols, cand_floor = dict(cols), dict(floor)
        for _ in range(rnd.choice([1, 1, 1, 2, 3])):
            if rnd.random() < 0.75:
                name = rnd.choice(PORTS)
                cand_cols[name] = max(1, min(400, cand_cols[name] + rnd.choice(
                    [-24, -12, -6, -3, -1, 1, 3, 6, 12, 24,
                     rnd.randint(-70, 70)])))
            else:
                key = rnd.choice(FLOOR_KEYS)
                cand_floor[key] = cand_floor[key] + rnd.choice(
                    [-12, -6, -3, -1, 1, 3, 6, 12])
        got = evaluate(cand_cols, cand_floor)
        if got is None:
            continue
        if (got[0], got[1] + got[2]) <= (cur[0], cur[1] + cur[2]):
            if got[0] < best[0][0]:
                best = (got, dict(cand_cols), dict(cand_floor))
            cols, floor, cur = cand_cols, cand_floor, got
            accepted += 1
    return best, accepted


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=2000)
    ap.add_argument("--restarts", type=int, default=8)
    args = ap.parse_args()
    overall = None
    for r in range(args.restarts):
        best, acc = search(args.iters, args.seed + r,
                           start=None if overall is None
                           else (overall[1], overall[2]))
        print(f"restart {r}: box {best[0][0]:,} foot {best[0][1]}x{best[0][2]} "
              f"controller {best[0][3]}x{best[0][4]} rail {best[0][5]} "
              f"(accepted {acc})", flush=True)
        print("  ports =", dict(sorted(best[1].items(), key=lambda kv: kv[1])),
              flush=True)
        print("  floor =", best[2], flush=True)
        if overall is None or best[0][0] < overall[0][0]:
            overall = best
    (box, w, h, cw, ch, nr), cols, floor = overall
    print(f"\nBEST box {box:,}  footprint {w}x{h}  controller {cw}x{ch}")
    print("ports =", dict(sorted(cols.items(), key=lambda kv: kv[1])))
    print("floor =", floor)
    # the walk itself only lints; the winner is the one config worth an oracle
    # round-trip, and it still has to be graded before anyone believes it
    ok = evaluate(cols, floor, verify=True) if "code_x" not in dir() else None
    print("oracle bindings:", "OK" if ok else "FAILED / re-check by grading")
