#!/usr/bin/env python3
"""Oracle-sized probe for the Pathfinder B-register wavefront workers.

Input is ``unvisited candidate``. The UNVIS worker computes
``take = unvisited & candidate`` and broadcasts it with S. Two independent
accumulator workers OR the take into their persistent B registers. All three
then park, allowing --inspect to verify arbitrary signed i64 state.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import littleman as lm


OUT = "/tmp/pathfinder-wave-workers.man"
LM = os.path.join(ROOT, "interp", "target", "release", "lm")


def build(repetitions=1):
    p = lm.Program()

    # UNVIS: read initial U into B, then process candidate directions in strict
    # U,R,D,L order. Every accepted mask is broadcast to the layer accumulator;
    # updating B after each direction enforces the parent tie-break.
    body = "r&SW~W" * repetitions
    width = len(body) + 8
    p.room(0, 0, width, 5)
    p.text(1, 1, "@rM" + body + "v")
    p.put(len(body) + 4, 2, "<")
    p.put(2, 2, "r")

    # Two copies exercise S broadcast. In the complete design these are the
    # direction's parent-mask worker and the shared NEXT accumulator.
    accumulator = ("r|M" * repetitions) + "v"
    accumulator_width = len(accumulator) + 6
    right_x = max(width, accumulator_width) + 2
    for x in (0, right_x):
        p.room(x, 9, accumulator_width, 5)
        p.text(x + 1, 10, "@0M>" + accumulator)
        p.put(x + 4 + len(accumulator), 11, "<")
        p.put(x + 2, 11, "r")

    # Input reaches the UNVIS room from above.
    p.input_room(1, -5)
    p.pipe([(2, -2), (2, -1)])

    # S broadcasts take to both accumulators.
    p.pipe([(5, 5), (5, 8)])
    p.pipe([(6, 5), (6, 7), (right_x + 5, 7), (right_x + 5, 8)])
    return p


def inspect(unvisited, candidates, tick=200):
    program = build(len(candidates))
    program.save(OUT)
    result = subprocess.run(
        [
            LM,
            f"--inspect={tick}",
            OUT,
            f"--input={' '.join(map(str, [unvisited, *candidates]))}",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def main():
    cases = [
        (0b111011, 0b101101),
        ((1 << 63) - 1, 0x5555555555555555),
        (-1, -(1 << 63)),
        (-0x123456789ABCDEF, 0x0F0F0F0F0F0F0F0F),
    ]
    for unvisited, candidate in cases:
        snap = inspect(unvisited, [candidate])
        take = unvisited & candidate
        new_unvisited = unvisited ^ take
        runners = sorted(snap["runners"], key=lambda runner: runner["id"])
        got = [runner["b"] for runner in runners]
        want = [new_unvisited, take, take]
        assert got == want, (unvisited, candidate, got, want, snap)
        print(f"PASS U={unvisited} C={candidate}: take={take} nextU={new_unvisited}")
    print("PASS wave worker arbitrary-i64 state and S broadcast")

    priority_cases = [
        (0xFF, [0x0F, 0x33, 0x55, 0xAA]),
        (-1, [-(1 << 63), 0x7FFF000000000000, 0x00FFFF0000000000, -1]),
        (-0x123456789ABCDEF, [0x5555555555555555, -1, 0x3333333333333333, 0]),
    ]
    for unvisited, candidates in priority_cases:
        remaining = unvisited
        accepted = []
        for candidate in candidates:
            take = remaining & candidate
            accepted.append(take)
            remaining ^= take
        frontier = 0
        for take in accepted:
            frontier |= take
        snap = inspect(unvisited, candidates)
        runners = sorted(snap["runners"], key=lambda runner: runner["id"])
        got = [runner["b"] for runner in runners]
        want = [remaining, frontier, frontier]
        assert got == want, (unvisited, candidates, accepted, got, want, snap)
        print(
            f"PASS priority U={unvisited}: accepted={accepted} "
            f"next={frontier} remaining={remaining}"
        )
    print("PASS U/R/D/L priority subtraction and four-input layer barrier")


if __name__ == "__main__":
    main()
