#!/usr/bin/env python3
"""Prove a UNVIS lane walking across four distinct candidate ports.

Each input room sees the same five-token stream ``U, Cu, Cr, Cd, Cl``. Tiny
selectors forward one token apiece. The state worker physically visits the
five receive positions, which avoids nearest-pipe lock-in, applies candidates
in U/R/D/L order, and sends four accepted masks to a NEXT accumulator.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import littleman as lm


OUT = "/tmp/pathfinder-lane-ports.man"
LM = os.path.join(ROOT, "interp", "target", "release", "lm")


def build():
    p = lm.Program()
    ports = [5, 20, 35, 50, 65]

    # One legal input room feeds a wide broadcaster. Each S copies the stream
    # item into all five selector pipes.
    p.input_room(28, -12)
    p.room(0, -7, 75, 5)
    p.text(25, -6, "@rSrSrSrSrS")
    p.put(37, -6, ">")
    p.put(38, -6, "v")
    p.put(38, -5, "<")
    p.put(37, -5, "^")
    p.put(26, -5, "r")
    p.pipe([(29, -9), (29, -8)])

    # Five selectors independently observe the input stream and forward their
    # assigned item. Blocking reads make their startup data-driven.
    for index, x in enumerate(ports):
        p.room(x - 4, 0, 13, 5)
        code = (
            "@"
            + ("r" * (index + 1))
            + "M"
            + ("r" * (4 - index))
            + "Ws"
        )
        p.text(x - 3, 1, code)
        loop_x = x + 6
        p.put(loop_x, 1, ">")
        p.put(loop_x + 1, 1, "v")
        p.put(loop_x + 1, 2, "<")
        p.put(loop_x, 2, "^")
        p.put(x - 2, 2, "r")
        p.pipe([(x, -2), (x, -1)])
        p.pipe([(x, 5), (x, 11)])

    # B starts as U. Four separated receive sites enforce U/R/D/L ordering.
    p.room(0, 12, 75, 5)
    p.text(1, 13, "@")
    p.put(ports[0], 13, "r")
    p.put(ports[0] + 1, 13, "M")
    for x in ports[1:]:
        p.text(x, 13, "r&sW~W")
    p.put(ports[-1] + 7, 13, ">")
    p.put(ports[-1] + 8, 13, "v")
    p.put(ports[-1] + 8, 14, "<")
    p.put(ports[-1] + 7, 14, "^")

    # All four lowercase sends share this sole outgoing pipe.
    p.room(20, 21, 20, 5)
    p.text(21, 22, "@0M>r|Mr|Mr|Mr|Mv")
    p.put(37, 23, "<")
    p.put(22, 23, "r")
    p.pipe([(32, 17), (32, 20)])
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
        state = runners[-2]["b"]
        accumulated = runners[-1]["b"]
        assert (state, accumulated) == (remaining, frontier), (
            values,
            remaining,
            frontier,
            snap,
        )
        print(
            f"PASS U={values[0]} candidates={values[1:]}: "
            f"remaining={remaining} next={frontier}"
        )
    print("PASS four distinct ordered candidate ports", program.footprint())


if __name__ == "__main__":
    main()
