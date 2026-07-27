#!/usr/bin/env python3
"""Mode-tagged update/query chain for one Pathfinder parent row.

Four persistent B registers store U/R/D/L parent words.  The ordinary BFS
packet is unchanged except for a leading positive mode token:

    [1, U, R, D, L, state]

Each room forwards the packet and ORs only its own TAKE into B.  Reconstruction
uses a negative mode and four copies of the selected row mask:

    [-1, mask, mask, mask, mask]

Room i forwards earlier hits, computes ``B & mask`` without modifying B, and
forwards the remaining masks.  The final reply is:

    [-1, hitU, hitR, hitD, hitL]

The sign tag makes a single X split sufficient: positive takes the update
half-loop and negative takes the query half-loop.  This probe deliberately
uses spacious 7x18 rooms; it establishes semantics before folding the branch.
"""

import os
import random
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import littleman as lm


LM = os.path.join(ROOT, "interp", "target", "release", "lm")
OUT = "/tmp/pathfinder-parent-query.man"


def _put_ops(program, positions, ops):
    assert len(ops) <= len(positions), (len(ops), len(positions))
    for position, op in zip(positions, ops):
        program.put(*position, op)


def parent_room(program, x, y, direction):
    """Build one persistent, mode-tagged parent service."""
    width, height = 7, 18
    right = x + width - 2
    bottom = y + height - 2
    mid = y + 8
    program.room(x, y, width, height)

    # Shared mode receive/forward and sign branch.
    program.put(x + 1, mid, ">")
    program.put(x + 2, mid, "@")
    program.put(x + 3, mid, "r")
    program.put(x + 4, mid, "s")
    program.put(right, mid, "X")

    # Positive/update half-loop: down, west, then north to the shared entry.
    program.put(right, bottom, "<")
    program.put(x + 1, bottom, "^")
    update_positions = []
    update_positions.extend((right, row) for row in range(mid + 1, bottom))
    update_positions.extend((col, bottom) for col in range(right - 1, x + 1, -1))
    update_positions.extend((x + 1, row) for row in range(bottom - 1, mid, -1))
    update_ops = ["r", "s"] * direction
    update_ops += ["r", "s", "|", "M"]
    update_ops += ["r", "s"] * (4 - direction)
    assert len(update_ops) == 12
    _put_ops(program, update_positions, update_ops)

    # Negative/query half-loop: up, west, then south to the shared entry.
    program.put(right, y + 1, "<")
    program.put(x + 1, y + 1, "v")
    query_positions = []
    query_positions.extend((right, row) for row in range(mid - 1, y + 1, -1))
    query_positions.extend((col, y + 1) for col in range(right - 1, x + 1, -1))
    query_positions.extend((x + 1, row) for row in range(y + 2, mid))
    query_ops = ["r", "s"] * direction
    query_ops += ["r", "&", "s"]
    query_ops += ["r", "s"] * (3 - direction)
    assert len(query_ops) == 9
    _put_ops(program, query_positions, query_ops)


def build():
    program = lm.Program()
    y = 5
    room_x = [5 + 9 * index for index in range(4)]
    for direction, x in enumerate(room_x):
        parent_room(program, x, y, direction)

    # Input enters U; the canonical stream then crosses U -> R -> D -> L.
    program.input_room(0, y + 7)
    program.pipe([(3, y + 8), (4, y + 8)])
    for left, right in zip(room_x, room_x[1:]):
        program.pipe([(left + 7, y + 8), (right - 1, y + 8)])

    program.output_room(room_x[-1] + 11, y + 7)
    program.pipe([
        (room_x[-1] + 7, y + 8),
        (room_x[-1] + 10, y + 8),
    ])
    return program


def reference(packets):
    parents = [0, 0, 0, 0]
    output = []
    for packet in packets:
        if packet[0] > 0:
            assert len(packet) == 6
            for direction in range(4):
                parents[direction] |= packet[direction + 1]
            output.extend(packet)
        else:
            assert packet[0] < 0 and len(packet) == 5
            mask = packet[1]
            assert packet[1:] == [mask] * 4
            output.extend([-1] + [word & mask for word in parents])
    return output, parents


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
        [[1, 0, 0, 0, 0, 0], [-1, 32768, 32768, 32768, 32768]],
        [
            [1, 3, 5, 9, 17, 123],
            [1, 4, 8, 16, 32, 456],
            [-1, 12, 12, 12, 12],
            [-1, 33, 33, 33, 33],
        ],
    ]
    rng = random.Random(0xA11CE)
    for _ in range(20):
        packets = []
        for _ in range(rng.randrange(1, 8)):
            packets.append([1] + [rng.randrange(65536) for _ in range(5)])
        for _ in range(rng.randrange(1, 5)):
            mask = 1 << rng.randrange(16)
            packets.append([-1, mask, mask, mask, mask])
        cases.append(packets)

    for packets in cases:
        run_case(packets)

    print(f"PASS parent update/query chain ({len(cases)} cases)")
    print("footprint:", program.footprint())


if __name__ == "__main__":
    main()
