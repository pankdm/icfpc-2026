#!/usr/bin/env python3
"""Joint search over Snake's controller port columns and satellite floorplan.

The controller's height is the number of boustrophedon *rows*, and a row ends
whenever the next op's Voronoi band lies behind the cursor.  Band geometry is
therefore the dominant term, and it is set entirely by the port columns -- which
`stateflow.COMPACT_PORTS` fixes by hand.  The two hottest ports (`sc`, `rr`) are
in different Voronoi families, so their bands may *overlap*; making `sc` the
westernmost `s` port and `rr` an early `r` port gives the load/store engine a
long shared run and collapses the wrap count.

The satellite floor is what limits how far the columns can move, so this search
optimises both together and uses the real builder as its feasibility oracle: a
proposal that collides is simply rejected (`littleman.Program.put` asserts, the
router raises).  Objective is the whole footprint box.

  python3 solutions/snake/search_rail.py --iters 4000
"""

import argparse
import copy
import os
import random
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))
sys.path.insert(0, HERE)

import build_rail  # noqa: E402
import manlint  # noqa: E402
import stateflow  # noqa: E402

PORTS = ["ri", "sp", "rp", "sc", "rr", "sd", "sa", "ss", "cc", "cr"]
FLOOR_KEYS = ["scalar_off", "cell_off", "ctop", "sp_row", "ri_row",
              "sc_band", "cc_band", "rr_band", "cr_band", "rp_band",
              "sd_band", "ss_band"]
BAND_KEYS = ["sc_band", "cc_band", "rr_band", "cr_band", "rp_band"]

BASE_PORTS = {n: stateflow.COMPACT_PORTS[n][0] for n in PORTS}
BASE_FLOOR = dict(scalar_off=24, cell_off=112, ctop=5, sp_row=8, ri_row=12,
                  sc_band=1, cc_band=2, rr_band=3, cr_band=3, rp_band=5,
                  sd_band=8, ss_band=20)

# The banked RAM servers attach their reply pipes *inside* their own component,
# so even a correct build reports a few loose pipe ends.  The reference is the
# baseline's loose-end SET (pipe index + side), not its count: a count budget
# lets a candidate fix one known end and break a real one for free.

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def smoke(program, slug, case):
    """Settle tick of one public case under the Rust interpreter, or None.

    This is not only a correctness gate (a grid can load cleanly and then
    deadlock, which no static check sees) -- it is the *objective*.  Moving port
    columns to shorten the controller spreads the hot ops over more columns, so
    the man walks farther: the first dense snake candidate cut the box 19% and
    raised average ticks 22%, for a 1.3% score gain.  Box alone is the wrong
    thing to minimise; score is box x ticks.

    One short case tracks the public average closely enough to steer on
    (24,932/182,390 = 0.137 for the baseline, 30,255/221,846 = 0.136 for that
    candidate), and costs ~0.3s against a 1.3s full grade.
    """
    import json
    import subprocess
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".man")
    os.close(fd)
    try:
        program.save(path)
        out = subprocess.run(
            ["node", os.path.join(REPO, "sim", "rust_case.js"), slug, path, case],
            capture_output=True, text=True, cwd=REPO, timeout=180)
        got = json.loads(out.stdout.strip().splitlines()[-1])
        return got["settleTick"] if got.get("status") == "pass" else None
    except Exception:
        return None

SMOKE_CASE = "game over at the wall"
BASE_DANGLING = None


def evaluate(cols, floor, code_x=10, verify=False, box_ceiling=None):
    """Box of the built program, or None when the proposal is infeasible.

    ``Program.pipe`` and ``Program.room`` overwrite silently, so a colliding
    floorplan only shows up as a loader error much later.  Any clobber that is
    not wall-glyph-on-wall-glyph (room corners, shared walls) rejects the
    proposal; both hand-built baselines score zero on that measure.
    """
    if len(set(cols.values())) != len(cols):
        return None
    spec = {n: (cols[n], stateflow.COMPACT_PORTS[n][1]) for n in PORTS}
    try:
        program, layout = build_rail.build(
            code_x=code_x, verify=False, ports=spec, floor=floor)
    except Exception:
        return None
    if manlint.bad_overwrites(program):
        return None
    if manlint.literal_faults(program.render().split("\n")):
        return None
    global BASE_DANGLING
    loose = manlint.dangling_signature(program)
    if BASE_DANGLING is None:
        BASE_DANGLING = loose
    elif loose != BASE_DANGLING:
        return None
    w, h, box = program.footprint()
    if box_ceiling is not None and box > box_ceiling:
        return None          # cannot win even at zero ticks; skip the run
    ticks = smoke(program, "snake", SMOKE_CASE)
    if ticks is None:
        return None
    if verify:
        try:
            build_rail.railflow.verify_bindings(program, layout)
        except Exception:
            return None
    return box * ticks, box, ticks, w, h, layout["width"], layout["height"]


def search(iters, seed, code_x, start=None):
    rnd = random.Random(seed)
    cols = dict(BASE_PORTS) if start is None else dict(start[0])
    floor = dict(BASE_FLOOR) if start is None else dict(start[1])
    cur = evaluate(cols, floor, code_x)
    assert cur is not None, "baseline is infeasible"
    best = (cur, dict(cols), dict(floor))
    print(f"  start score {cur[0]:,} = box {cur[1]:,} x {cur[2]:,} ticks",
          flush=True)
    accepted = 0
    for step in range(iters):
        cand_cols, cand_floor = dict(cols), dict(floor)
        for _ in range(rnd.choice([1, 1, 1, 2, 3])):
            if rnd.random() < 0.82:
                name = rnd.choice(PORTS)
                delta = rnd.choice([-16, -8, -4, -2, -1, 1, 2, 4, 8, 16,
                                    rnd.randint(-45, 45)])
                cand_cols[name] = max(1, min(240, cand_cols[name] + delta))
            else:
                key = rnd.choice(FLOOR_KEYS)
                lo = 1 if key in BAND_KEYS else 0
                cand_floor[key] = max(lo, cand_floor[key]
                                      + rnd.choice([-8, -4, -2, -1, 1, 2, 4, 8]))
        # a proposal can only win by shrinking box x ticks, so anything whose
        # box alone already exceeds the incumbent score / a floor on ticks is
        # rejected before paying for an interpreter run
        got = evaluate(cand_cols, cand_floor, code_x,
                       box_ceiling=cur[0] // max(1, cur[2] // 2))
        if got is None:
            continue
        # sideways moves are accepted so the walk can leave a plateau; only
        # strictly better boxes become the champion, and those are re-checked
        # against the oracle's own pipe topology before being believed.
        # Descend on (box, semi-perimeter): plain box has huge plateaus that a
        # random walk drifts across until the footprint is much worse than where
        # it started, and only the shorter side moving does anything for the box.
        if got[0] <= cur[0]:
            if got[0] < best[0][0]:
                best = (got, dict(cand_cols), dict(cand_floor))
                print(f"  score {got[0]:,} = box {got[1]:,} x {got[2]:,} ticks",
                      flush=True)
            cols, floor, cur = cand_cols, cand_floor, got
            accepted += 1
    return best, accepted


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=1000)
    ap.add_argument("--restarts", type=int, default=6)
    ap.add_argument("--code-x", type=int, default=10)
    args = ap.parse_args()
    overall = None
    for r in range(args.restarts):
        # every restart resumes from the best floorplan found so far, with a
        # fresh random stream: the moves are single-knob, so a plateau exit that
        # one seed cannot find another usually can
        best, acc = search(args.iters, args.seed + r, args.code_x,
                           start=None if overall is None
                           else (overall[1], overall[2]))
        print(f"restart {r}: score {best[0][0]:,} box {best[0][1]:,} "
              f"ticks {best[0][2]:,} foot {best[0][3]}x{best[0][4]} "
              f"controller {best[0][5]}x{best[0][6]} (accepted {acc})",
              flush=True)
        print("  ports =", dict(sorted(best[1].items(), key=lambda kv: kv[1])),
              flush=True)
        print("  floor =", best[2], flush=True)
        if overall is None or best[0][0] < overall[0][0]:
            overall = best
    (score, box, ticks, w, h, cw, ch), cols, floor = overall
    print(f"\nBEST score {score:,} = box {box:,} x {ticks:,} ticks  "
          f"footprint {w}x{h}  controller {cw}x{ch}")
    print("ports =", dict(sorted(cols.items(), key=lambda kv: kv[1])))
    print("floor =", floor)
    # the walk itself only lints; the winner is the one config worth an oracle
    # round-trip, and it still has to be graded before anyone believes it
    ok = evaluate(cols, floor, args.code_x, verify=True)
    print("oracle bindings:", "OK" if ok else "FAILED / re-check by grading")
