#!/usr/bin/env python3
"""Pitch-nine update/query/reset parent service for Pathfinder.

This is the same proven protocol as ``pathfinder_parent_query.py``, folded
from width 10 to width 9 so sixteen row services fit the original 149-wide
wavefront controller:

    positive [1,U,R,D,L,state]  update and forward
    negative [-1,m,m,m,m]      query and return hits
    zero     [0]                reset

At the sign branch A is already zero on reset, so one ``M`` is sufficient;
the spacious proof's preceding literal ``0`` was redundant.  Removing it
creates the turn cell needed to fit the reset chord in a seven-cell interior.
"""

import os
import random
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "scratchpad"))

import littleman as lm

from pathfinder_parent_query import _put_ops, reference


LM = os.path.join(ROOT, "interp", "target", "release", "lm")
OUT = "/tmp/pathfinder-parent-query-compact.man"


def parent_room_compact(program, x, y, direction):
    """Build one 9x14 persistent parent service."""
    width, height = 9, 14
    bottom = y + height - 2
    mid = y + 5
    branch_x = x + 5
    program.room(x, y, width, height)

    program.put(x + 1, mid, ">")
    program.put(x + 2, mid, "@")
    program.put(x + 3, mid, "r")
    program.put(x + 4, mid, "s")
    program.put(branch_x, mid, "X")

    # Positive/update lap.
    program.put(branch_x, bottom, "<")
    program.put(x + 1, bottom, "^")
    update_positions = []
    update_positions.extend((branch_x, row) for row in range(mid + 1, bottom))
    update_positions.extend(
        (col, bottom) for col in range(branch_x - 1, x + 1, -1)
    )
    update_positions.extend(
        (x + 1, row) for row in range(bottom - 1, mid, -1)
    )
    reset_row = mid + 2
    update_positions = [
        position for position in update_positions
        if position[1] != reset_row
    ]
    update_ops = ["r", "s"] * direction
    update_ops += ["r", "s", "|", "M"]
    update_ops += ["r", "s"] * (4 - direction)
    _put_ops(program, update_positions, update_ops)

    # Negative/query lap.
    program.put(branch_x, y + 1, "<")
    program.put(x + 1, y + 1, "v")
    query_positions = []
    query_positions.extend(
        (branch_x, row) for row in range(mid - 1, y + 1, -1)
    )
    query_positions.extend(
        (col, y + 1) for col in range(branch_x - 1, x + 1, -1)
    )
    query_positions.extend((x + 1, row) for row in range(y + 2, mid))
    query_ops = ["r", "s"] * direction
    query_ops += ["r", "&", "s"]
    query_ops += ["r", "s"] * (3 - direction)
    _put_ops(program, query_positions, query_ops)

    # Zero/reset chord.  X guarantees A=0, hence M alone clears B.
    program.put(branch_x + 1, mid, "M")
    program.put(branch_x + 2, mid, "v")
    program.put(branch_x + 2, reset_row, "<")
    program.put(x + 1, reset_row, "^")


def build():
    program = lm.Program()
    y = 5
    room_x = [5 + 11 * index for index in range(4)]
    for direction, x in enumerate(room_x):
        parent_room_compact(program, x, y, direction)

    program.input_room(0, y + 4)
    program.pipe([(3, y + 5), (4, y + 5)])
    for left, right in zip(room_x, room_x[1:]):
        program.pipe([(left + 9, y + 5), (right - 1, y + 5)])
    program.output_room(room_x[-1] + 13, y + 4)
    program.pipe([(room_x[-1] + 9, y + 5), (room_x[-1] + 12, y + 5)])
    return program


def run_case(packets):
    inputs = [value for packet in packets for value in packet]
    expected, parents = reference(packets)
    result = subprocess.run(
        [
            LM,
            "--grade",
            OUT,
            "--cap=20000",
            "--input=" + " ".join(map(str, inputs)),
            "--expected=" + " ".join(map(str, expected)),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert '"status":"pass"' in result.stdout, (result.stdout, packets, expected)
    return parents


def main():
    program = build()
    program.save(OUT)
    cases = [
        [[1, 1, 2, 4, 8, 65535], [-1, 1, 1, 1, 1]],
        [
            [1, 3, 5, 9, 17, 123],
            [1, 4, 8, 16, 32, 456],
            [-1, 12, 12, 12, 12],
            [0],
            [-1, 12, 12, 12, 12],
        ],
    ]
    rng = random.Random(0xC09AC7)
    for _ in range(20):
        packets = []
        for _ in range(rng.randrange(1, 8)):
            packets.append([1] + [rng.randrange(65536) for _ in range(5)])
        if rng.randrange(2):
            packets.append([0])
        for _ in range(rng.randrange(1, 5)):
            mask = 1 << rng.randrange(16)
            packets.append([-1, mask, mask, mask, mask])
        cases.append(packets)
    for packets in cases:
        run_case(packets)
    print(f"PASS compact parent update/query chain ({len(cases)} cases)")
    print("footprint:", program.footprint())


if __name__ == "__main__":
    main()
