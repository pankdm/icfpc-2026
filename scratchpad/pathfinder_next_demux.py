#!/usr/bin/env python3
"""NEXT service with update/query/reset dispatch for Pathfinder bitplanes.

Input packets:
  positive [1, U, R, L, D, state] -> update output [state, frontier]
  negative [-1, hitU, hitR, hitL, hitD] -> query output unchanged
  zero [0] -> consumed, no output

This spacious probe proves the protocol and separate-pipe binding before the
room is folded into the sixteen-lane kernel.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import littleman as lm


LM = os.path.join(ROOT, "interp", "target", "release", "lm")
OUT = "/tmp/pathfinder-next-demux.man"


def _put(program, positions, ops):
    assert len(ops) <= len(positions), (len(ops), len(positions))
    for position, op in zip(positions, ops):
        program.put(*position, op)


def next_demux_room(program, x, y):
    """Build a correctness-first 14x21 three-way NEXT service."""
    width, height = 14, 21
    branch_x = x + 8
    mid = y + 9
    bottom = y + height - 2
    reset_row = mid + 2
    program.room(x, y, width, height)

    program.put(x + 1, mid, ">")
    program.put(x + 2, mid, "@")
    program.put(x + 3, mid, "r")
    program.put(branch_x, mid, "X")

    # Positive: union four candidates, exclude state, emit state/frontier.
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
    update_positions = [
        position for position in update_positions
        if position[1] != reset_row
    ]
    update_ops = ["0", "M"]
    for _ in range(4):
        update_ops += ["r", "|", "M"]
    update_ops += ["r", "~", "s", "W", "s"]
    _put(program, update_positions, update_ops)

    # Negative: forward mode and all four directional hits unchanged.
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
    _put(program, query_positions, ["s"] + ["r", "s"] * 4)

    # Zero: clear scratch B and return without touching either output pipe.
    program.put(branch_x + 1, mid, "M")
    program.put(branch_x + 2, mid, "v")
    program.put(branch_x + 2, reset_row, "<")
    program.put(x + 1, reset_row, "^")


def next_demux_room_compact(program, x, y, broadcast_last=False):
    """Nine-column fold of NEXT; height buys the nineteen update slots."""
    width, height = 9, 21
    branch_x = x + 5
    mid = y + 6
    bottom = y + height - 2
    reset_row = mid + 2
    program.room(x, y, width, height)
    program.put(x + 1, mid, ">")
    program.put(x + 2, mid, "@")
    program.put(x + 3, mid, "r")
    program.put(branch_x, mid, "X")

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
    update_positions = [
        position for position in update_positions
        if position[1] != reset_row
    ]
    update_ops = ["0", "M"]
    for _ in range(4):
        update_ops += ["r", "|", "M"]
    update_ops += ["r", "~", "s", "W", "S" if broadcast_last else "s"]
    _put(program, update_positions, update_ops)

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
    _put(program, query_positions, ["s"] + ["r", "s"] * 4)

    program.put(branch_x + 1, mid, "M")
    program.put(branch_x + 2, mid, "v")
    program.put(branch_x + 2, reset_row, "<")
    program.put(x + 1, reset_row, "^")


def build(compact=True):
    program = lm.Program()
    x, y = 8, 8
    builder = next_demux_room_compact if compact else next_demux_room
    builder(program, x, y)
    mid = y + (6 if compact else 9)
    height = 21

    program.input_room(0, mid - 1)
    program.pipe([(3, mid), (x - 1, mid)])

    # Query leaves the top and update the bottom.  A tiny R/S merge room
    # serializes its two incoming pipes into the one legal output pipe.
    merge_x, merge_y = x + 22, y + 6
    program.room(merge_x, merge_y, 7, 7)
    program.text(merge_x + 1, merge_y + 1, ">@RSv")
    program.put(merge_x + 5, merge_y + 5, "<")
    program.put(merge_x + 1, merge_y + 5, "^")
    query_x = x + 3
    update_x = x + 3
    program.pipe([
        (query_x, y - 1),
        (x + 3, y - 3),
        (merge_x + 3, y - 3),
        (merge_x + 3, merge_y - 1),
    ])
    program.pipe([
        (update_x, y + height),
        (update_x, y + height + 2),
        (merge_x + 3, y + 23),
        (merge_x + 3, merge_y + 7),
    ])
    program.output_room(merge_x + 10, merge_y + 2)
    program.pipe([
        (merge_x + 7, merge_y + 3),
        (merge_x + 9, merge_y + 3),
    ])
    return program


def main():
    program = build()
    program.save(OUT)
    inputs = [
        1, 1, 2, 4, 8, 3,
        -1, 16, 32, 64, 128,
        0,
        1, 8, 4, 2, 1, 7,
        -1, 1, 2, 4, 8,
    ]
    # The probe's merge makes the two independent result channels observable
    # through one legal output room.  Query's shorter path overtakes the
    # second token of each update; the real solver does not merge them.
    expected = [
        12,
        -1, 16, 32, 64, 128,
        -1, 1, 2, 4, 8,
        15, 8, 15,
    ]
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
    assert '"status":"pass"' in result.stdout, result.stdout
    print("PASS NEXT update/query/reset demux")
    print("footprint:", program.footprint())


if __name__ == "__main__":
    main()
