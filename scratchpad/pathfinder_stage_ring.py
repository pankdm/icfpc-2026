#!/usr/bin/env python3
"""Compact staged U/R/D/L lane protocol.

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


def loop(p, x, y):
    p.put(x, y, ">")
    p.put(x + 1, y, "v")
    p.put(x + 1, y + 1, "<")
    p.put(x, y + 1, "^")


def build():
    p = lm.Program()
    stage_x = [0, 23, 46, 69]
    # Controller sends U,Cu,Cr,Cd,Cl through five distinct bottom ports.
    state_port = 2
    candidate_ports = [8, 31, 54, 77]
    ports = [state_port, *candidate_ports]
    p.input_room(39, -5)
    p.room(0, 0, 89, 5)
    p.text(1, 1, "@")
    cursor = 2
    for port in ports:
        while cursor < port:
            cursor += 1
        p.put(port, 1, "r")
        p.put(port + 1, 1, "s")
        cursor = port + 1
        p.pipe([(port + 1, 5), (port + 1, 8)])
    loop(p, 82, 1)
    p.pipe([(40, -2), (40, -1)])

    # Four priority stages. The first state arrives from above; later state
    # words arrive through the west wall.
    for index, x in enumerate(stage_x):
        p.room(x, 9, 21, 5)
        p.text(x + 1, 10, "@rM")
        p.put(x + 8, 10, "r")
        p.text(x + 9, 10, "&sW~WW")
        p.put(x + 17, 10, "s")
        loop(p, x + 18, 10)
        # Accepted subset to NEXT.
        p.pipe([(x + 10, 14), (x + 10, 17)])
        if index < 3:
            p.pipe([(x + 21, 10), (x + 22, 10)])

    # Initial state attaches at the first stage's state read.
    # (The controller pipe was already placed above x=3.)

    # Final reduced state sink.
    p.room(92, 9, 12, 5)
    p.text(93, 10, "@rMv")
    p.put(96, 11, "<")
    p.put(94, 11, "r")
    p.pipe([(90, 10), (91, 10)])

    # Four-input NEXT barrier/OR.
    p.room(0, 18, 89, 5)
    p.text(1, 19, "@0M>R|MR|MR|MR|Mv")
    p.put(17, 20, "<")
    p.put(2, 20, "R")
    return p


def inspect(values, tick=300):
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
        [0xFF, 0x0F, 0x33, 0x55, 0xAA],
        [-1, -(1 << 63), 0x7FFF000000000000, 0x00FFFF0000000000, -1],
        [-0x123456789ABCDEF, 0x5555555555555555, -1, 0x3333333333333333, 0],
    ]
    for values in cases:
        remaining = values[0]
        frontier = 0
        for candidate in values[1:]:
            take = remaining & candidate
            frontier |= take
            remaining ^= take
        snap, program = inspect(values)
        assert snap.get("end") not in ("loaderror", "fatal"), snap
        runners = sorted(snap["runners"], key=lambda runner: runner["id"])
        # controller, four stages, final-state sink, NEXT
        got = (runners[-2]["b"], runners[-1]["b"])
        assert got == (remaining, frontier), (values, got, remaining, frontier, snap)
        print(f"PASS {values}: remaining={remaining} next={frontier}")
    print("PASS staged U/R/D/L lane", program.footprint())


if __name__ == "__main__":
    main()
