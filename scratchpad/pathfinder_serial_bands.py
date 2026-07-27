#!/usr/bin/env python3
"""Four serialized Pathfinder priority bands at the proven nine-cell pitch.

For each of sixteen independent row lanes, stage ``d`` forwards the earlier
TAKE prefix, consumes UNVIS, applies its candidate, then appends
``TAKE_d, reduced_UNVIS``.  The physical stream evolves as:

    U:  [U, state]
    R:  [U, R, state]
    D:  [U, R, D, state]
    L:  [U, R, D, L, state]

All stage traffic therefore uses one pipe pair per lane.  Fixed one-bit
candidates keep this probe focused on stream order and priority subtraction;
the separate stage-band probe validates a distinct candidate input.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import littleman as lm


OUT = "/tmp/pathfinder-serial-bands.man"
LM = os.path.join(ROOT, "interp", "target", "release", "lm")
LANES = 16
PITCH = 9
ROOM_W = 8


def perimeter_slots(x, y, h):
    """Instruction slots around a clockwise interior perimeter."""
    bottom = y + h - 2
    slots = []
    slots.extend((cx, y + 1) for cx in range(x + 2, x + 6))
    slots.extend((x + 6, cy) for cy in range(y + 2, bottom))
    slots.extend((cx, bottom) for cx in range(x + 5, x + 1, -1))
    slots.extend((x + 1, cy) for cy in range(bottom - 1, y + 1, -1))
    return slots


def stage_room(p, x, y, index, candidate):
    """Stamp one cyclic stage and return its stream input/output columns."""
    h = 5 + index
    p.room(x, y, ROOM_W, h)
    bottom = y + h - 2
    p.put(x + 1, y + 1, ">")
    p.put(x + 6, y + 1, "v")
    p.put(x + 6, bottom, "<")
    p.put(x + 1, bottom, "^")

    ops = ["@"] + ["r", "s"] * index
    ops += ["r", "M", str(candidate), "&", "s", "W", "~", "s"]
    slots = perimeter_slots(x, y, h)
    assert len(ops) <= len(slots), (index, len(ops), len(slots))
    for (cx, cy), op in zip(slots, ops):
        p.put(cx, cy, op)
    return x + 6, x + 2, h


def connect_stream(p, x, source_y, source_h, dest_y):
    """Bottom output column x+2 to next top input column x+6."""
    src = (x + 2, source_y + source_h)
    dst = (x + 6, dest_y - 1)
    mid = source_y + source_h + 1
    p.pipe([src, (x + 2, mid), (x + 6, mid), dst])


def build():
    p = lm.Program()
    stage_y = (7, 15, 24, 34)
    candidates = (1, 2, 4, 8)

    # Initial per-lane UNVIS sources.
    for lane in range(LANES):
        x = lane * PITCH
        state = 31 + lane
        p.room(x, 0, ROOM_W, 4)
        p.text(x + 1, 1, f"@{state % 10}sH")

    stage_meta = []
    for direction, (y, candidate) in enumerate(zip(stage_y, candidates)):
        band = []
        for lane in range(LANES):
            x = lane * PITCH
            inp, out, h = stage_room(p, x, y, direction, candidate)
            band.append((inp, out, h))
        stage_meta.append(band)

    # Source -> U, then U -> R -> D -> L.
    for lane in range(LANES):
        x = lane * PITCH
        p.pipe([(x + 3, 4), (x + 3, 5), (x + 6, 5), (x + 6, 6)])
        for direction in range(3):
            source_y = stage_y[direction]
            source_h = stage_meta[direction][lane][2]
            connect_stream(p, x, source_y, source_h, stage_y[direction + 1])

    # Passive sinks provide enough pipe capacity for all five final tokens.
    sink_y = 50
    for lane in range(LANES):
        x = lane * PITCH
        p.room(x, sink_y, ROOM_W, 3)
        l_h = stage_meta[3][lane][2]
        p.pipe([(x + 2, stage_y[3] + l_h), (x + 2, sink_y - 1)])
    return p


def inspect(tick=500):
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

    final_pipes = [
        pipe for pipe in snapshot["pipes"]
        if pipe["dst"][1] == 49
    ]
    assert len(final_pipes) == LANES, (len(final_pipes), snapshot)
    final_pipes.sort(key=lambda pipe: pipe["dst"][0])

    for lane, pipe in enumerate(final_pipes):
        state = (31 + lane) % 10
        remaining = state
        takes = []
        for candidate in (1, 2, 4, 8):
            take = remaining & candidate
            remaining ^= take
            takes.append(take)
        # Older values sit farther along the pipe.
        got = [
            item["value"]
            for item in sorted(pipe["values"] or [], key=lambda item: -item["index"])
        ]
        assert got == [*takes, remaining], (lane, got, takes, remaining, snapshot)

    print(f"PASS four serialized bands, {LANES} lanes at pitch {PITCH}")
    print("footprint:", program.footprint())


if __name__ == "__main__":
    main()
