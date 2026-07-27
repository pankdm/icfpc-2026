#!/usr/bin/env python3
"""Close the 16 serialized Pathfinder lanes across multiple BFS layers.

The L band emits ``[U,R,D,L,state]``.  Two serial consumers preserve the
single-stream invariant:

* PARENT ORs every TAKE into persistent parent state and forwards all five
  words unchanged;
* NEXT ORs the four TAKE words, retains the complete frontier, and sends only
  state up the spare ninth column to seed U for the following layer.

This probe intentionally keeps fixed candidates.  Its job is to prove that
the 143-wide band can run persistently without a timer or another TAKE pipe.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import littleman as lm

from pathfinder_serial_bands import (
    LANES,
    PITCH,
)


OUT = "/tmp/pathfinder-cyclic-bands.man"
LM = os.path.join(ROOT, "interp", "target", "release", "lm")
ROOM_W = 7


def perimeter_slots(x, y, h):
    """Instruction slots around a clockwise width-seven interior perimeter."""
    right = x + ROOM_W - 2
    bottom = y + h - 2
    slots = []
    slots.extend((cx, y + 1) for cx in range(x + 2, right))
    slots.extend((right, cy) for cy in range(y + 2, bottom))
    slots.extend((cx, bottom) for cx in range(right - 1, x + 1, -1))
    slots.extend((x + 1, cy) for cy in range(bottom - 1, y + 1, -1))
    return slots


def loop_room(p, x, y, h, ops):
    """Stamp a clockwise room and place ops around its interior perimeter."""
    p.room(x, y, ROOM_W, h)
    bottom = y + h - 2
    p.put(x + 1, y + 1, ">")
    p.put(x + 5, y + 1, "v")
    p.put(x + 5, bottom, "<")
    p.put(x + 1, bottom, "^")
    slots = perimeter_slots(x, y, h)
    assert len(ops) <= len(slots), (len(ops), len(slots), h)
    for (cx, cy), op in zip(slots, ops):
        p.put(cx, cy, op)


def stage_room(p, x, y, index, candidate):
    """Width-seven priority stage; extra height replaces the deleted column."""
    h = 6 + index
    p.room(x, y, ROOM_W, h)
    bottom = y + h - 2
    p.put(x + 1, y + 1, ">")
    p.put(x + 5, y + 1, "v")
    p.put(x + 5, bottom, "<")
    p.put(x + 1, bottom, "^")
    ops = ["@"] + ["r", "s"] * index
    ops += ["r", "M", str(candidate), "&", "s", "W", "~", "s"]
    slots = perimeter_slots(x, y, h)
    assert len(ops) <= len(slots), (index, len(ops), len(slots))
    for (cx, cy), op in zip(slots, ops):
        p.put(cx, cy, op)
    return x + 5, x + 2, h


def connect_stream(p, x, source_y, source_h, dest_y):
    """Bottom output column x+2 to next top input column x+5."""
    src = (x + 2, source_y + source_h)
    dst = (x + 5, dest_y - 1)
    mid = source_y + source_h + 1
    p.pipe([src, (x + 2, mid), (x + 5, mid), dst])


def build():
    p = lm.Program()

    source_y = 0
    merge_y = 6
    stage_y = (14, 23, 33, 44)
    candidates = (1, 2, 4, 8)
    parent_y = 56
    next_y = 70

    # A one-shot source and the cyclic return both feed an uppercase merge.
    # U sees only the merge's single output pipe, avoiding lowercase-port
    # lock-in after the seed has drained.
    for lane in range(LANES):
        x = lane * PITCH
        p.room(x, source_y, ROOM_W, 4)
        p.text(x + 1, source_y + 1, ">@7sH")
        loop_room(p, x, merge_y, 5, ["@", "R", "s"])

    stage_meta = []
    for direction, (y, candidate) in enumerate(zip(stage_y, candidates)):
        band = []
        for lane in range(LANES):
            x = lane * PITCH
            inp, out, h = stage_room(p, x, y, direction, candidate)
            band.append((inp, out, h))
        stage_meta.append(band)

    for lane in range(LANES):
        x = lane * PITCH

        # Seed -> merge; merge -> U; then U -> R -> D -> L.
        p.pipe([(x + 4, source_y + 4), (x + 4, merge_y - 1)])
        p.pipe([
            (x + 3, merge_y + 5),
            (x + 3, stage_y[0] - 1),
        ])
        for direction in range(3):
            connect_stream(
                p,
                x,
                stage_y[direction],
                stage_meta[direction][lane][2],
                stage_y[direction + 1],
            )

        # PARENT forwards the canonical stream while accumulating every TAKE
        # ever observed in B.  The fifth state word is forwarded unchanged but
        # deliberately excluded from the accumulator.
        parent_ops = ["@"]
        for _ in range(4):
            parent_ops += ["r", "s", "|", "M"]
        parent_ops += ["r", "s"]
        loop_room(p, x, parent_y, 11, parent_ops)
        l_h = stage_meta[3][lane][2]
        p.pipe([
            (x + 2, stage_y[3] + l_h),
            (x + 2, parent_y - 1),
        ])

        # NEXT computes the complete frontier in B, then forwards only the
        # fifth state word.  Fixed candidates make B an observation point;
        # the next probe will distribute that frontier to real neighbours.
        loop_room(
            p,
            x,
            next_y,
            10,
            [
                "@", "0", "M",
                "r", "|", "M",
                "r", "|", "M",
                "r", "|", "M",
                "r", "|", "M",
                "r", "s",
            ],
        )
        p.pipe([(x + 2, parent_y + 11), (x + 2, next_y - 1)])

        # Returned UNVIS leaves NEXT at the bottom, bends into the free ninth
        # column, rises beside every band, then enters the merge from below.
        p.pipe([
            (x + 5, next_y + 10),
            (x + 5, next_y + 11),
            (x + 7, next_y + 11),
            (x + 7, merge_y + 6),
            (x + 4, merge_y + 6),
            (x + 4, merge_y + 5),
        ])

    return p


def inspect(tick=3000):
    program = build()
    program.save(OUT)
    result = subprocess.run(
        [LM, f"--inspect={tick}", OUT],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout), program


def main():
    snapshot, program = inspect()
    assert snapshot.get("end") not in ("loaderror", "fatal"), snapshot

    # Runner order is source, merge, U/R/D/L, parent, NEXT for each band of
    # sixteen.  Parent B must retain the first layer's discovered bits even
    # after many all-zero layers have traversed the complete return cycle.
    parent_runners = [
        runner
        for runner in snapshot["runners"]
        if LANES * 6 <= runner["id"] < LANES * 7
    ]
    assert len(parent_runners) == LANES, len(parent_runners)
    for lane, runner in enumerate(parent_runners):
        assert runner["b"] == 7, (lane, runner, snapshot)

    print(f"PASS persistent cyclic bands, {LANES} lanes at pitch {PITCH}")
    print("footprint:", program.footprint())


if __name__ == "__main__":
    main()
