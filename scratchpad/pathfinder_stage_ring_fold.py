#!/usr/bin/env python3
"""Folded, persistent Pathfinder U/R/D/L lane with parent accumulation.

This is the physical bridge between ``pathfinder_stage_ring.py`` and a complete
four-word wavefront machine:

* the four priority stages are folded into a 2x2 snake;
* every accepted mask is forwarded to its persistent direction-parent
  accumulator;
* two consecutive layers exercise the same workers and state chain.

The persistent NEXT barrier is independently proved by
``pathfinder_stage_ring.py``.  Keeping that return bundle out of this probe
lets the fold's topology be checked without a diagnostic pipe overwriting the
stage-2 -> stage-3 state link.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from layout import Layout, auto_pipe


OUT = "/tmp/pathfinder-stage-ring-fold.man"
LM = os.path.join(ROOT, "interp", "target", "release", "lm")


def _loop_east(L, x0, x1, y):
    L.put(x1, y, "v")
    L.put(x1, y + 1, "<")
    L.put(x0, y + 1, "^")


def _loop_west(L, x0, x1, y):
    L.put(x0, y, "v")
    L.put(x0, y + 1, ">")
    L.put(x1, y + 1, "^")


def build():
    L = Layout()
    p = L.p
    occupied = set()

    def room(x, y, w, h):
        rect = p.room(x, y, w, h)
        occupied.update(
            (cx, cy)
            for cx in range(rect.x0, rect.x1 + 1)
            for cy in range(rect.y0, rect.y1 + 1)
        )
        return rect

    def input_room(x, y):
        rect = p.input_room(x, y)
        occupied.update(
            (cx, cy)
            for cx in range(rect.x0, rect.x1 + 1)
            for cy in range(rect.y0, rect.y1 + 1)
        )
        return rect

    def pipe(src, dst, margin=12):
        blocked = occupied | {cell for cell, glyph in p.cells.items() if glyph != " "}
        return auto_pipe(L, src, dst, occupied=blocked, margin=margin)

    # Five-token dispatcher per layer: U, Cu share the first lane, then
    # Cr/Cd/Cl use one lane each.  Deleting the separate U pipe is the same
    # canonical-stream trick used by Snake's state ring.
    input_room(24, -5)
    room(0, 0, 52, 5)
    L.put(1, 1, ">")
    L.put(2, 1, "@")
    for x, ch in (
        (3, "r"), (4, "s"),
        (6, "r"), (7, "s"),
        (10, "r"), (14, "s"),
        (16, "r"), (34, "s"),
        (36, "r"), (44, "s"),
    ):
        L.put(x, 1, ch)
    _loop_east(L, 1, 48, 1)

    # Stage code.  Each stage receives state then candidate, sends TAKE through
    # the near bottom port, and sends reduced state through the side port.
    stage_xy = [(0, 10), (27, 10), (27, 26), (0, 26)]
    for index, (x, y) in enumerate(stage_xy):
        room(x, y, 20, 5)
        if index < 2:
            L.hrun(x + 1, y + 1, ">@rM")
            L.put(x + 7, y + 1, "r")
            L.hrun(x + 8, y + 1, "&sW~WW")
            L.put(x + 16, y + 1, "s")
            _loop_east(L, x + 1, x + 17, y + 1)
        elif index == 2:
            # Stamp the west-heading execution stream explicitly.
            L.put(x + 17, y + 1, "@")
            L.put(x + 18, y + 1, "<")
            L.put(x + 16, y + 1, "r")
            L.put(x + 15, y + 1, "M")
            L.put(x + 11, y + 1, "r")
            for off, ch in enumerate("&sW~WW"):
                L.put(x + 10 - off, y + 1, ch)
            L.put(x + 2, y + 1, "s")
            _loop_west(L, x + 1, x + 18, y + 1)
        else:
            # The last stage takes its candidate from the LEFT wall.  This
            # frees the fold's top/bottom routing cut for the NEXT bundle.
            L.put(x + 17, y + 1, "@")
            L.put(x + 18, y + 1, "<")
            L.put(x + 16, y + 1, "r")
            L.put(x + 15, y + 1, "M")
            L.put(x + 9, y + 1, "r")
            for off, ch in enumerate("&sW~WW"):
                L.put(x + 8 - off, y + 1, ch)
            # Retain the final reduced word locally in B for this probe.
            L.put(x + 2, y + 1, "M")
            _loop_west(L, x + 1, x + 18, y + 1)

    # TAKE broadcast relays, two in the fold and two immediately below it.
    relay_xy = [(5, 17), (32, 17), (32, 33), (5, 33)]
    for x, y in relay_xy:
        room(x, y, 10, 5)
        L.hrun(x + 1, y + 1, ">@rS")
        _loop_east(L, x + 1, x + 6, y + 1)

    # Four persistent direction-parent accumulators.
    parent_xy = [(-10, 16), (53, 16), (53, 33), (-10, 33)]
    for x, y in parent_xy:
        room(x, y, 10, 5)
        # B starts at zero and persists; do not clear it on the return loop.
        L.hrun(x + 1, y + 1, ">@r|M")
        _loop_east(L, x + 1, x + 8, y + 1)

    # State chain first: these short links are topology-critical.
    pipe((19, 11), (27, 11), margin=4)
    p.pipe([(47, 11), (70, 11), (70, 27), (47, 27)])
    p.pipe([(26, 27), (23, 27), (23, 29), (21, 29), (21, 28), (20, 28)])

    # TAKE -> relay uses the two-cell gap directly.
    p.pipe([(9, 15), (9, 16)])
    p.pipe([(36, 15), (36, 16)])
    p.pipe([(36, 31), (36, 32)])
    p.pipe([(7, 31), (7, 32)])

    # Reserve the four short parent legs before the longer global nets.
    p.pipe([(4, 18), (0, 18)])
    p.pipe([(42, 18), (52, 18)])
    p.pipe([(42, 35), (52, 35)])
    p.pipe([(4, 35), (0, 35)])

    # Input and dispatcher outputs.
    pipe((25, -3), (25, 0), margin=4)
    p.pipe([(4, 5), (4, 9)])
    p.pipe([(14, 5), (14, 7), (36, 7), (36, 9)])
    p.pipe([(34, 5), (34, 6), (73, 6), (73, 32), (38, 32), (38, 31)])
    p.pipe([(44, -1), (44, -8), (-12, -8), (-12, 28), (-1, 28)])

    return p


def inspect(values, tick=3000):
    program = build()
    program.save(OUT)
    result = subprocess.run(
        [LM, f"--inspect={tick}", OUT, f"--input={' '.join(map(str, values))}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout), program


def main():
    cases = [
        [
            [0xFF, 0x0F, 0x33, 0x55, 0xAA],
            [0xFFFF, 0x00FF, 0x0F0F, 0x3333, 0xAAAA],
        ],
        [
            [-1, -(1 << 63), 0x7FFF000000000000, 0x00FFFF0000000000, -1],
            [-1, 0x5555555555555555, 0x3333333333333333, -1, 0],
        ],
    ]
    for layers in cases:
        remaining = layers[0][0]
        parents = [0, 0, 0, 0]
        for values in layers:
            remaining = values[0]
            nxt = 0
            for direction, candidate in enumerate(values[1:]):
                take = remaining & candidate
                remaining ^= take
                nxt |= take
                parents[direction] |= take
        snap, program = inspect([v for layer in layers for v in layer])
        assert snap.get("end") not in ("loaderror", "fatal"), snap
        runners = sorted(snap["runners"], key=lambda runner: runner["id"])
        # dispatcher, 4 stages, 4 relays, 4 parents
        got_parents = [runners[i]["b"] for i in (3, 4, 12, 9)]
        got_state = runners[7]["b"]
        assert got_parents == parents, (got_parents, parents, snap)
        assert got_state == remaining, (got_state, remaining, snap)
        print(
            f"PASS two layers: state={got_state} parents={got_parents}"
        )
    print("PASS folded persistent lane + parents", program.footprint())


if __name__ == "__main__":
    main()
