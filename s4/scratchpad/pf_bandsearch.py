#!/usr/bin/env python3
"""Fast model of pathfinder's controller geometry, then search port columns.

``railflow._lay_once`` is the whole geometry story: it places 1768 ops on a
boustrophedon and every time the next port op's Voronoi band lies behind the
cursor it burns a row.  It is pure Python and takes ~10ms, so we can search port
columns thousands of times per second WITHOUT building the RAM satellites.

Reports rows / width for the baseline, then anneals the 12 port columns to
minimise (rows, width).  Winners still have to go through build_rail + manlint +
a real case; this only proposes.

    cd s4 && python3 scratchpad/pf_bandsearch.py [--iters N]
"""
import argparse
import os
import random
import sys
import time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
FORK = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(FORK, "tools"))
sys.path.insert(0, os.path.join(FORK, "solutions", "pathfinder"))

import railflow  # noqa: E402
import stateflow  # noqa: E402
from boustro import voronoi_bands, Conflict  # noqa: E402
import build_bitset5  # noqa: E402
from build_reflow_banked import alias_empty_gotos  # noqa: E402

FLOW = alias_empty_gotos(build_bitset5.build_flow())
LABELS = list(FLOW.blocks)
PORTS = list(stateflow.DEFAULT_PORTS)
GLYPH = {n: stateflow.DEFAULT_PORTS[n][1] for n in PORTS}
CODE_X = 0
NRAIL = 10


def geometry(cols, op_slack=0, lit_forbid=()):
    """rows, width of the code block for a port->column map (no rail alloc)."""
    bands = {}
    bands.update(voronoi_bands([(n, c) for n, c in cols.items()
                                if GLYPH[n] == "s"]))
    bands.update(voronoi_bands([(n, c) for n, c in cols.items()
                                if GLYPH[n] == "r"]))
    opmax = max(cols.values()) + op_slack
    cursor, entry, items, intent = railflow._lay_once(
        FLOW, LABELS, cols, GLYPH, bands, 0, 0, NRAIL, opmax,
        lit_forbid, pad_after=())
    max_y = max(y for _, y in cursor.cells)
    # The satellites can stick out east of the last port: the queue serpentine
    # alone is ~34 columns past qs.  Charging only the controller's width is how
    # a 290-wide proposal turned into a 320-wide grid.
    width = max(opmax + 2, *(hi + 2 for _, hi in component_boxes(cols)))
    return max_y + 2, width


BASE = {n: stateflow.DEFAULT_PORTS[n][0] for n in PORTS}
FORBID = set(range(40, 70)) | set(range(156, 184))


def component_boxes(c):
    """Measured x-extent of each satellite, once its offset is pinned to its
    port: scratch 8 wide, banked scalar RAM 34, packed cell RAM 72 (proxy +
    main + 9 belts), display 18, queue relay + serpentine 34."""
    return [(c["sp"] - 3, c["sp"] + 5), (c["sc"] - 3, c["sc"] + 31),
            (c["cc"] - 3, c["cc"] + 69), (c["sa"] - 8, c["sa"] + 10),
            # measured on dense-e: room at qs-2, serpentine 267..281 for
            # qs=274, i.e. qs-7..qs+7.  The old qs+32 was the legacy
            # queue_rows=6 shape and overcharged the width by 25 columns.
            (c["qs"] - 8, c["qs"] + 10)]


def routable(c):
    """Orderings the hand-written satellite floorplan can actually wire.

    Each request/reply service occupies a horizontal slot below the controller
    and hands out a command attachment WEST of its reply attachment.  The
    command port's descent to the command row crosses every horizontal run in
    between, so the reply's westbound run must not span the command column --
    which forces  send port < component < receive port  for each service:

        sc < scalar RAM  < rr        sp < scratch < rp        cc < cell RAM < cr

    Measured: this is exactly the invariant the baseline map satisfies, and
    violating it is what left the 73,984-box candidate with an unfixable
    collision at the scalar command column.
    """
    # ``ri`` is deliberately NOT a group: with ri_row=2 its pipe is a single
    # cell below the wall, so no horizontal band can run into it.
    groups = [("sp", "rp"), ("sc", "rr"), ("cc", "cr"),
              ("sd", "sa"), ("qs", "qr")]
    spans = []
    for g in groups:
        lo, hi = min(c[n] for n in g), max(c[n] for n in g)
        spans.append((lo, hi, g))
    spans.sort()
    for (lo, hi, _), (lo2, _, _) in zip(spans, spans[1:]):
        if hi >= lo2:
            return False
    # ss's feeder is the deepest run on the floor, so it may pass over the
    # shallow command/reply bands -- it only has to stay east of the cell RAM.
    if c["ss"] <= c["cr"]:
        return False
    if not (c["sc"] + 12 <= c["rr"]
            and c["sp"] + 6 <= c["rp"]
            and c["cc"] + 25 <= c["cr"]
            and c["sd"] < c["sa"]
            and c["qs"] > c["cr"] and c["qr"] > c["cr"]):
        return False
    # Components are stamped side by side in the band under the controller, and
    # each one's x is pinned to the port it serves (a feeder that is not
    # zero-length is a run that crosses somebody).  Measured extents, relative
    # to the pinned offset: scratch 8 wide, banked scalar RAM 34, packed cell
    # RAM 72 (proxy + main + 9 belts), display 18, queue relay + serpentine 34.
    boxes = sorted(component_boxes(c))
    if not all(a[1] < b[0] for a, b in zip(boxes, boxes[1:])):
        return False
    # Measured the hard way: `routable` used to model only the request/reply
    # ordering, so it happily returned port maps whose scratch room started at
    # x=-1 or whose 3-wide input room landed INSIDE the scalar RAM.  Both build
    # and then fail, which is what left the first derived floorplan with no
    # clean configuration at all.
    if min(lo for lo, _ in component_boxes(c)) < 0:
        return False
    return all(c["ri"] + 1 < lo or c["ri"] - 1 > hi
               for lo, hi in component_boxes(c))


def placeable(c):
    """Relaxed feasibility: only the five COMPONENT boxes have to fit.

    Each service's component is pinned under its command ('s') port so that
    feeder is zero-length; the reply ('r') port is free, because its feeder is a
    horizontal run in its own band row above every component, and a descent that
    turns at band row b never reaches a component that starts below ctop.  That
    is the whole content of the old ``routable`` ordering rule, and exposing the
    band rows in stateflow.build_program is what makes dropping it legal.
    """
    boxes = component_boxes(c)
    if min(lo for lo, _ in boxes) < 0:
        return False
    ordered = sorted(boxes)
    if not all(a[1] < b[0] for a, b in zip(ordered, ordered[1:])):
        return False
    # ri, sd and ss descend PAST the band rows -- ri into its own input room,
    # sd and ss down to the display's west/bottom walls -- so unlike the reply
    # ports they need a column no component occupies.  Leaving sd out of this
    # is how the first placeable winner put sd at column 147 inside its own
    # display room.
    for name in ("ri", "sd", "ss"):
        if not all(c[name] + 1 < lo or c[name] - 1 > hi for lo, hi in boxes):
            return False
    # sd/ss reach the display along a row below the scalar RAM but level with
    # the cell RAM, so they must approach from the display's own side of it
    cell_lo, cell_hi = c["cc"] - 3, c["cc"] + 69
    for name in ("sd", "ss"):
        if (c[name] < cell_lo) != (c["sa"] < cell_lo):
            return False
        if cell_lo < c[name] < cell_hi:
            return False
    # the queue's return pipe is its capacity; keep the serpentine east of
    # everything so ``queue_rows`` can still buy cells without moving a room
    return c["qs"] == max(c[n] for n in ("sp", "sc", "cc", "sa", "qs"))


def report_transitions(cols):
    """Which consecutive banded-op pairs burn rows?"""
    bands = {}
    bands.update(voronoi_bands([(n, c) for n, c in cols.items()
                                if GLYPH[n] == "s"]))
    bands.update(voronoi_bands([(n, c) for n, c in cols.items()
                                if GLYPH[n] == "r"]))
    pairs = Counter()
    for lb in LABELS:
        prev = None
        for t in FLOW.blocks[lb]:
            if isinstance(t, tuple):
                break
            if t in cols:
                if prev is not None:
                    pairs[(prev, t)] += 1
                prev = t
    return pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--satellite", type=int, default=64,
                    help="rows of satellites below the controller")
    ap.add_argument("--restarts", type=int, default=6)
    ap.add_argument("--keep-order", action="store_true",
                    help="forbid moves that reorder the port columns, so the "
                         "floor's pipe bands stay routable")
    ap.add_argument("--start", default=None, help="json port->col to start from")
    ap.add_argument("--placeable", action="store_true",
                    help="only the five component boxes must fit; reply ports "
                         "are free (needs the exposed band rows)")
    ap.add_argument("--routable", action="store_true",
                    help="only orderings the satellite floorplan can wire")
    args = ap.parse_args()
    global BASE
    if args.start:
        import json
        BASE = {n: json.loads(args.start).get(n, BASE[n]) for n in PORTS}
    base_order = [n for n, _ in sorted(BASE.items(), key=lambda kv: kv[1])]

    t0 = time.time()
    rows, width = geometry(BASE, 0, FORBID)
    print(f"baseline: rows {rows} width {width}  ({time.time()-t0:.3f}s/eval)")
    pairs = report_transitions(BASE)
    print("top banded transitions:", pairs.most_common(12))

    def cost(cols):
        try:
            r, w = geometry(cols, 0, FORBID)
        except Conflict:
            return None
        return max(w, r + args.satellite) ** 2, r, w

    best = None
    rnd = random.Random(args.seed)
    for rs in range(args.restarts):
        cur_cols = dict(BASE) if best is None else dict(best[1])
        cur = cost(cur_cols)
        for it in range(args.iters):
            cand = dict(cur_cols)
            for _ in range(rnd.choice([1, 1, 1, 2, 3])):
                n = rnd.choice(PORTS)
                cand[n] = max(1, min(400, cand[n] + rnd.choice(
                    [-32, -16, -8, -4, -2, -1, 1, 2, 4, 8, 16, 32,
                     rnd.randint(-80, 80)])))
            if len(set(cand.values())) != len(cand):
                continue
            if args.routable and not routable(cand):
                continue
            if args.placeable and not placeable(cand):
                continue
            if args.keep_order and [
                    n for n, _ in sorted(cand.items(),
                                         key=lambda kv: kv[1])] != base_order:
                continue
            got = cost(cand)
            if got is None:
                continue
            if got[0] <= cur[0]:
                cur_cols, cur = cand, got
                if best is None or got[0] < best[0][0]:
                    best = (got, dict(cand))
        print(f"restart {rs}: best box {best[0][0]:,} rows {best[0][1]} "
              f"width {best[0][2]}", flush=True)
        print("  cols =", dict(sorted(best[1].items(), key=lambda kv: kv[1])),
              flush=True)
    print("\nBEST", best[0])
    print("cols =", dict(sorted(best[1].items(), key=lambda kv: kv[1])))


if __name__ == "__main__":
    main()
