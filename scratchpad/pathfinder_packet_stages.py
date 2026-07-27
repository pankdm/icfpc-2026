#!/usr/bin/env python3
"""Compose the streaming row driver with four real priority stages.

Input packets are ``[state,U,R,L,D]``.  Stage ``i`` forwards earlier TAKE
values, consumes its adjacent state/candidate pair, emits TAKE plus reduced
state, then forwards later candidates.  The stream therefore evolves as:

    [state,U,R,L,D]
    [U,state,R,L,D]
    [U,R,state,L,D]
    [U,R,L,state,D]
    [U,R,L,D,state]

Every stage has exactly fifteen operations and fits a 7×9 room.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "scratchpad"))

from pathfinder_stream_driver import (
    LANES,
    LM,
    PITCH,
    TILE0,
    build as build_driver,
)


OUT = "/tmp/pathfinder-packet-stages.man"
ROOM_W = 7


def perimeter_slots(x, y, h=9):
    right = x + 5
    bottom = y + h - 2
    slots = []
    slots.extend((cx, y + 1) for cx in range(x + 2, right))
    slots.extend((right, cy) for cy in range(y + 2, bottom))
    slots.extend((cx, bottom) for cx in range(right - 1, x + 1, -1))
    slots.extend((x + 1, cy) for cy in range(bottom - 1, y + 1, -1))
    return slots


def packet_stage(p, x, y, index):
    h = 9
    p.room(x, y, ROOM_W, h)
    bottom = y + h - 2
    p.put(x + 1, y + 1, ">")
    p.put(x + 5, y + 1, "v")
    p.put(x + 5, bottom, "<")
    p.put(x + 1, bottom, "^")

    ops = ["@"] + ["r", "s"] * index
    ops += ["r", "M", "r", "&", "s", "W", "~", "s"]
    ops += ["r", "s"] * (3 - index)
    slots = perimeter_slots(x, y, h)
    assert len(ops) == 15 and len(ops) <= len(slots)
    for (cx, cy), op in zip(slots, ops):
        p.put(cx, cy, op)


def build():
    p, frontiers, state = build_driver(with_sinks=False)
    stage_y = (34, 46, 58, 70)

    for lane in range(LANES):
        base = TILE0 + lane * PITCH
        x = base + 3
        packet_col = base + 6

        for index, y in enumerate(stage_y):
            packet_stage(p, x, y, index)

        # Driver -> U.
        p.pipe([(packet_col, 16), (packet_col, stage_y[0] - 1)])

        # Each stage's bottom-left output feeds the next stage's top-right
        # input. All routing remains inside the row's nine-column pitch.
        for index in range(3):
            y = stage_y[index]
            next_y = stage_y[index + 1]
            p.pipe([
                (x + 2, y + 9),
                (x + 2, y + 10),
                (x + 5, y + 10),
                (x + 5, next_y - 1),
            ])

        # Passive final sink for [U,R,L,D,state].
        p.room(x + 2, 85, 3, 3)
        p.pipe([
            (x + 2, stage_y[3] + 9),
            (x + 2, 83),
            (x + 3, 83),
            (x + 3, 84),
        ])

    return p, frontiers, state


def inspect(tick=3000):
    program, frontiers, state = build()
    program.save(OUT)
    result = subprocess.run(
        [LM, f"--inspect={tick}", OUT],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout), program, frontiers, state


def pipe_values(pipe):
    return [
        item["value"]
        for item in sorted(pipe.get("values") or [], key=lambda item: -item["index"])
    ]


def main():
    snapshot, program, frontiers, state = inspect()
    assert snapshot.get("end") not in ("loaderror", "fatal"), snapshot

    finals = sorted(
        (
            pipe
            for pipe in snapshot["pipes"]
            if pipe["dst"][1] == 84
        ),
        key=lambda pipe: pipe["dst"][0],
    )
    assert len(finals) == LANES, len(finals)
    for lane, pipe in enumerate(finals):
        candidates = [
            frontiers[lane - 1] if lane else 0,
            2 * frontiers[lane],
            frontiers[lane] // 2,
            frontiers[lane + 1] if lane + 1 < LANES else 0,
        ]
        remaining = state
        takes = []
        for candidate in candidates:
            take = remaining & candidate
            remaining ^= take
            takes.append(take)
        expected = [*takes, remaining]
        got = pipe_values(pipe)
        assert got == expected, (lane, got, expected, snapshot)

    print("PASS streaming driver + four packet stages")
    print("footprint:", program.footprint())


if __name__ == "__main__":
    main()
