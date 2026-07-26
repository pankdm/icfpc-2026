#!/usr/bin/env python3
"""Compact persistent staged U/R/D/L lane protocol.

The shrinking UNVIS word travels through four rooms. Each room consumes one
candidate, sends its accepted subset to NEXT, and forwards the reduced word.
This replaces one wide worker walking among four locked lowercase-read ports.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import littleman as lm


OUT = "/tmp/pathfinder-stage-ring.man"
LM = os.path.join(ROOT, "interp", "target", "release", "lm")


def return_loop(p, left, right, y):
    """Return an eastbound worker along the otherwise-empty row below."""
    p.put(right, y, "v")
    p.put(right, y + 1, "<")
    p.put(left, y + 1, "^")


def build():
    p = lm.Program()
    stage_x = [0, 23, 46, 69]
    # Controller sends U,Cu,Cr,Cd,Cl through five distinct bottom ports.
    state_port = 4
    candidate_ports = [8, 31, 54, 77]
    ports = [state_port, *candidate_ports]
    p.input_room(39, -5)
    p.room(0, 0, 89, 5)
    p.put(1, 1, ">")
    p.put(2, 1, "@")
    cursor = 2
    for port in ports:
        while cursor < port:
            cursor += 1
        p.put(port, 1, "r")
        p.put(port + 1, 1, "s")
        cursor = port + 1
        p.pipe([(port + 1, 5), (port + 1, 8)])
    return_loop(p, 1, 82, 1)
    p.pipe([(40, -2), (40, -1)])

    # Four priority stages. The first state arrives from above; later state
    # words arrive through the west wall.
    for index, x in enumerate(stage_x):
        p.room(x, 9, 21, 5)
        p.put(x + 1, 10, ">")
        p.text(x + 2, 10, "@rM")
        p.put(x + 8, 10, "r")
        p.text(x + 9, 10, "&sW~WW")
        p.put(x + 17, 10, "s")
        return_loop(p, x + 1, x + 18, 10)
        # Accepted subset to NEXT.
        p.pipe([(x + 10, 14), (x + 10, 17)])
        if index < 3:
            p.pipe([(x + 21, 10), (x + 22, 10)])

    # Initial state attaches at the first stage's state read.
    # (The controller pipe was already placed above x=3.)

    # Final reduced state sink.
    p.room(92, 9, 12, 5)
    p.put(93, 10, ">")
    p.text(94, 10, "@RM")
    return_loop(p, 93, 97, 10)
    p.put(95, 11, "R")
    p.pipe([(90, 10), (91, 10)])

    # Four-input NEXT barrier/OR.
    p.room(0, 18, 89, 5)
    p.put(1, 19, ">")
    p.text(2, 19, "@0M")
    for x in (10, 33, 56, 79):
        p.text(x, 19, "r|M")
    p.text(82, 19, "s0M")
    return_loop(p, 1, 85, 19)

    # Drain one completed NEXT word per layer and retain the newest one in B.
    p.room(38, 27, 14, 5)
    p.put(39, 28, ">")
    p.text(40, 28, "@RM")
    return_loop(p, 39, 43, 28)
    p.put(41, 29, "R")
    p.pipe([(82, 23), (82, 25), (41, 25), (41, 26)])
    return p


def inspect(values, tick=600):
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
        expected = []
        for values in layers:
            remaining = values[0]
            frontier = 0
            for candidate in values[1:]:
                take = remaining & candidate
                frontier |= take
                remaining ^= take
            expected.append((remaining, frontier))
        flat_values = [value for layer in layers for value in layer]
        snap, program = inspect(flat_values)
        assert snap.get("end") not in ("loaderror", "fatal"), snap
        runners = sorted(snap["runners"], key=lambda runner: runner["id"])
        # controller, four stages, final-state sink, NEXT, NEXT sink
        # A receive site retains the newest delivered value while it parks for
        # the next layer; inspect A rather than the previous completed B.
        got = (runners[-3]["a"], runners[-1]["a"])
        assert got == expected[-1], (layers, got, expected, snap)
        print(f"PASS two layers: expected={expected}, final={got}")
    print("PASS persistent staged U/R/D/L lane", program.footprint())


if __name__ == "__main__":
    main()
