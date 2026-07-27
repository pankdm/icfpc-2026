#!/usr/bin/env python3
"""Joint anneal of pathfinder's 12 port columns AND the satellite floorplan,
with SOFT structural penalties so the walk can cross infeasible ground.

``solutions/pathfinder/search_rail.py`` rejects any proposal that lints badly,
so it can only ever explore the connected component of the baseline floorplan.
The fast geometry model (`scratchpad/pf_bandsearch.py`) says the controller can
go 246->191 rows if the port ORDER is rebuilt -- which is exactly a move that
lints badly on the way.  This walker prices a lint fault instead of rejecting
it, so the order rebuild is reachable, and only reports configs that end up
structurally clean.

Cost is lexicographic: (structural faults, box, total pipe length).  Pipe length
is the tiebreak because pipe latency is what turned a -7% box into +8% ticks the
last time this layout moved.

    cd s4 && python3 scratchpad/pf_joint.py --iters 6000 --seed 1 --out best.json
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

import build_rail  # noqa: E402
import manlint  # noqa: E402
import railflow  # noqa: E402
import stateflow  # noqa: E402

PORTS = list(stateflow.DEFAULT_PORTS)
FLOOR_KEYS = ["scalar_off", "cell_off", "ctop", "scratch_off", "scratch_row",
              "ri_row", "display_off", "cc_band", "cr_band", "queue_off",
              "queue_row", "queue_left", "queue_tail", "sd_band", "sa_band",
              "ss_band", "queue_rows", "queue_right_off", "display_row"]
BASE_PORTS = {n: stateflow.DEFAULT_PORTS[n][0] for n in PORTS}
BASE_FLOOR = dict(scalar_off=48, cell_off=164, ctop=5, scratch_off=18,
                  scratch_row=12, ri_row=12, display_off=110, cc_band=1,
                  cr_band=3, queue_off=268, queue_row=6, queue_left=280,
                  queue_tail=266, sd_band=-4, sa_band=-3, ss_band=20,
                  queue_rows=1, queue_right_off=300, display_row=60)
QUEUE_FLOOR = 40
BASE_DANGLING = None


LM = os.path.join(os.path.dirname(FORK), "interp", "target", "release", "lm")
_TMP = os.path.join("/tmp", f"pf_loadcheck_{os.getpid()}.man")


def loader_ok(program):
    """Does the real loader accept this grid?  ~5 ms, and it is the only check
    that sees a component stamp burying a pipe under its own wall."""
    import subprocess
    program.save(_TMP)
    got = subprocess.run([LM, _TMP, "--grade", "--cap=200", "--input=1 1"],
                         capture_output=True, text=True)
    return "loaderror" not in got.stdout


def evaluate(cols, floor):
    """(faults, box, pipelen, w, h, cw, ch) or None when it will not build."""
    if len(set(cols.values())) != len(cols):
        return None
    shape = dict(floor)
    qrows = shape.pop("queue_rows", 1)
    qright = shape.pop("queue_right_off", 300)
    if qrows < 1 or qrows > 24:
        return None
    spec = {n: (cols[n], stateflow.DEFAULT_PORTS[n][1]) for n in PORTS}
    try:
        program, layout = build_rail.build(
            verify=False, ports=spec, floor=shape,
            queue_rows=qrows, queue_right_off=qright)
    except Exception:
        return None
    faults = len(manlint.bad_overwrites(program))
    global BASE_DANGLING
    loose = manlint.dangling_signature(program)
    if BASE_DANGLING is None:
        BASE_DANGLING = loose
    else:
        faults += len(loose ^ BASE_DANGLING)
    qr = layout["ports"]["qr"]
    queue = [rec[2] for rec in program.pipes if rec[1] == qr]
    if not queue:
        faults += 5
    elif min(queue) < QUEUE_FLOOR:
        faults += 1
    if faults == 0:
        faults += len(manlint.literal_faults(program.render().split("\n")))
    if faults == 0:
        import contextlib
        import io
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                railflow.verify_bindings(program, layout)
        except Exception:
            faults += 1
    if faults == 0 and not loader_ok(program):
        # The lints are necessary, not sufficient: a component room stamped
        # cell-by-cell can bury a pipe without ever calling `put` with a
        # different glyph.  The real loader answers in ~5 ms, which is 5% of a
        # build, so every otherwise-clean proposal pays for it.
        faults += 1
    w, h, box = program.footprint()
    pipelen = sum(rec[2] for rec in program.pipes)
    return (faults, box, pipelen, w, h, layout["width"], layout["height"])


def key(got):
    return (got[0], got[1], got[2])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=6000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--restarts", type=int, default=1)
    ap.add_argument("--start", default=None, help="json {ports:..,floor:..}")
    ap.add_argument("--out", default=None)
    ap.add_argument("--floor-only", action="store_true")
    ap.add_argument("--port-prob", type=float, default=0.55)
    args = ap.parse_args()

    cols, floor = dict(BASE_PORTS), dict(BASE_FLOOR)
    if args.start:
        blob = json.load(open(args.start))
        cols.update(blob.get("ports", {}))
        floor.update(blob.get("floor", {}))
    rnd = random.Random(args.seed)
    cur = evaluate(cols, floor)
    assert cur is not None
    print("start", key(cur), f"{cur[3]}x{cur[4]} ctrl {cur[5]}x{cur[6]}",
          flush=True)
    best = None
    t0 = time.time()
    for rs in range(args.restarts):
        for it in range(args.iters):
            cand_c, cand_f = dict(cols), dict(floor)
            for _ in range(rnd.choice([1, 1, 1, 2, 3])):
                if not args.floor_only and rnd.random() < args.port_prob:
                    n = rnd.choice(PORTS)
                    cand_c[n] = max(1, min(400, cand_c[n] + rnd.choice(
                        [-32, -16, -8, -4, -2, -1, 1, 2, 4, 8, 16, 32,
                         rnd.randint(-60, 60)])))
                else:
                    k = rnd.choice(FLOOR_KEYS)
                    cand_f[k] = cand_f[k] + rnd.choice(
                        [-32, -16, -8, -4, -2, -1, 1, 2, 4, 8, 16, 32])
            got = evaluate(cand_c, cand_f)
            if got is None:
                continue
            if key(got) <= key(cur):
                cols, floor, cur = cand_c, cand_f, got
                if got[0] == 0 and (best is None or key(got) < key(best[0])):
                    best = (got, dict(cand_c), dict(cand_f))
                    print(f"  [{it}] CLEAN box {got[1]:,} foot {got[3]}x{got[4]}"
                          f" ctrl {got[5]}x{got[6]} pipe {got[2]}",
                          flush=True)
                    if args.out:
                        # checkpoint every improvement: a long walk that is
                        # still running is otherwise unusable
                        json.dump({"ports": cand_c, "floor": cand_f},
                                  open(args.out, "w"), indent=1)
            if it % 1000 == 0:
                print(f"  it {it} cur {key(cur)} ({time.time()-t0:.0f}s)",
                      flush=True)
        # restart from the best clean point found so far
        if best is not None:
            cols, floor = dict(best[1]), dict(best[2])
            cur = evaluate(cols, floor)
    if best is None:
        print("no clean configuration found; last state", key(cur))
        print("ports =", json.dumps(cols))
        print("floor =", json.dumps(floor))
        shape = dict(floor)
        qrows = shape.pop("queue_rows", 1)
        qright = shape.pop("queue_right_off", 300)
        spec = {n: (cols[n], stateflow.DEFAULT_PORTS[n][1]) for n in PORTS}
        program, layout = build_rail.build(
            verify=False, ports=spec, floor=shape,
            queue_rows=qrows, queue_right_off=qright)
        for o in manlint.bad_overwrites(program)[:12]:
            print("  collision", o)
        loose = manlint.dangling_signature(program) ^ BASE_DANGLING
        if loose:
            print("  dangling", sorted(loose)[:12])
        if args.out:
            json.dump({"ports": cols, "floor": floor},
                      open(args.out, "w"), indent=1)
        return
    got, bc, bf = best
    print(f"\nBEST box {got[1]:,} foot {got[3]}x{got[4]} ctrl {got[5]}x{got[6]}")
    print("ports =", json.dumps(dict(sorted(bc.items(), key=lambda kv: kv[1]))))
    print("floor =", json.dumps(bf))
    if args.out:
        json.dump({"ports": bc, "floor": bf}, open(args.out, "w"), indent=1)


if __name__ == "__main__":
    main()
