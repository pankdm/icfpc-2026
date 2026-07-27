#!/usr/bin/env python3
"""Persistent OPEN-word store and seed/return merge for one Pathfinder row.

The row keeps its immutable OPEN mask in B and accepts one tagged input stream:

    [0, open]             setup: B := open
    [-1, flag]            seed:  emit [open XOR flag, flag]
    [1, state, frontier]  return: emit [state, frontier]

The output is exactly the pair expected by the streaming bitplane controller.
The mode token is consumed locally.  None of the seed or return paths modifies
B, so one setup packet is sufficient for every later round.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import littleman as lm


LM = os.path.join(ROOT, "interp", "target", "release", "lm")
OUT = "/tmp/pathfinder-seed-store.man"


def _put_ops(program, positions, ops):
    assert len(ops) <= len(positions), (len(ops), len(positions))
    for position, op in zip(positions, ops):
        program.put(*position, op)


def seed_store_room(program, x, y):
    """Build one persistent OPEN store and two-value seed/return merge."""
    width, height = 10, 18
    right = x + width - 2
    bottom = y + height - 2
    mid = y + 8
    branch_x = x + 5
    program.room(x, y, width, height)

    # Shared mode receive and sign branch.  Mode is deliberately not sent.
    program.put(x + 1, mid, ">")
    program.put(x + 2, mid, "@")
    program.put(x + 3, mid, "r")
    program.put(branch_x, mid, "X")

    # Positive/return: relay [state, frontier] without touching B.
    program.put(branch_x, bottom, "<")
    program.put(x + 1, bottom, "^")
    return_positions = []
    return_positions.extend((branch_x, row) for row in range(mid + 1, bottom))
    return_positions.extend(
        (col, bottom) for col in range(branch_x - 1, x + 1, -1)
    )
    return_positions.extend(
        (x + 1, row) for row in range(bottom - 1, mid, -1)
    )

    # Setup's straight chord crosses this column.  Leave its crossing cell
    # direction-neutral for both paths.
    setup_row = mid + 2
    return_positions = [
        position for position in return_positions if position[1] != setup_row
    ]
    _put_ops(program, return_positions, ["r", "s", "r", "s"])

    # Negative/seed: r flag; XOR with persistent OPEN, emit state; XOR again
    # to recover and emit flag.  XOR never modifies B.
    program.put(branch_x, y + 1, "<")
    program.put(x + 1, y + 1, "v")
    seed_positions = []
    seed_positions.extend(
        (branch_x, row) for row in range(mid - 1, y + 1, -1)
    )
    seed_positions.extend(
        (col, y + 1) for col in range(branch_x - 1, x + 1, -1)
    )
    seed_positions.extend((x + 1, row) for row in range(y + 2, mid))
    _put_ops(program, seed_positions, ["r", "~", "s", "~", "s"])

    # Zero/setup: receive OPEN into A, copy it to persistent B, then rejoin.
    program.put(branch_x + 1, mid, "r")
    program.put(branch_x + 2, mid, "M")
    program.put(branch_x + 3, mid, "v")
    program.put(branch_x + 3, setup_row, "<")
    program.put(x + 1, setup_row, "^")


def build():
    program = lm.Program()
    x, y = 5, 5
    seed_store_room(program, x, y)

    program.input_room(0, y + 7)
    program.pipe([(3, y + 8), (4, y + 8)])

    program.output_room(x + 14, y + 7)
    program.pipe([(x + 10, y + 8), (x + 13, y + 8)])
    return program


def reference(packets):
    open_word = 0
    output = []
    for packet in packets:
        if packet[0] == 0:
            assert len(packet) == 2
            open_word = packet[1]
        elif packet[0] < 0:
            assert len(packet) == 2
            flag = packet[1]
            output.extend([open_word ^ flag, flag])
        else:
            assert len(packet) == 3
            output.extend(packet[1:])
    return output


def main():
    packets = [
        [0, 0xA55A],
        [-1, 0x0020],
        [1, 0x1234, 0x0040],
        [-1, 0x8000],
        [0, 0x0F0F],
        [-1, 0x0001],
        [1, 0x7777, 0],
    ]
    expected = reference(packets)
    values = [value for packet in packets for value in packet]

    program = build()
    program.save(OUT)
    result = subprocess.run(
        [
            LM,
            "--grade",
            OUT,
            "--cap=10000",
            "--input=" + " ".join(map(str, values)),
            "--expected=" + " ".join(map(str, expected)),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    verdict = json.loads(result.stdout)
    assert verdict["status"] == "pass", (verdict, expected)
    print("PASS persistent seed store:", expected)
    print("settle:", verdict["settleTick"])
    print("footprint:", program.footprint())


if __name__ == "__main__":
    main()
