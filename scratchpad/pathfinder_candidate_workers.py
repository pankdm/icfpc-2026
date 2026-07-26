#!/usr/bin/env python3
"""Physical probe for a cross-word Pathfinder candidate.

Two persistent workers consume the same ``local, neighbour`` broadcast.  One
forms ``local << 16`` and the other forms ``neighbour >> 48``; an any-ready
accumulator ORs both contributions.  This is the U-candidate shape used between
adjacent 64-bit lanes.  The probe deliberately includes negative words.
"""

import importlib.util
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import littleman as lm


OUT = "/tmp/pathfinder-candidate-workers.man"
LM = os.path.join(ROOT, "interp", "target", "release", "lm")
MASK64 = (1 << 64) - 1


def signed(value):
    value &= MASK64
    return value - (1 << 64) if value >= (1 << 63) else value


def build():
    p = lm.Program()

    # Input relay broadcasts both words to both contribution workers.
    p.room(8, 0, 12, 5)
    p.text(9, 1, "@rSrSv")
    p.put(14, 2, "<")
    p.put(10, 2, "r")
    p.input_room(9, -5)
    p.pipe([(10, -2), (10, -1)])

    # Local contribution. It consumes only the first word.
    p.room(0, 9, 18, 5)
    p.text(1, 10, "@rM`16`W{srv")
    p.put(12, 11, "<")
    p.put(2, 11, "r")

    # Cross-word contribution. Discard local, then consume neighbour.
    p.room(22, 9, 26, 5)
    p.text(23, 10, "@rrM`48`W}M`65535`&sv")
    p.put(43, 11, "<")
    p.put(24, 11, "r")

    # Relay S broadcasts to both contribution rooms.
    p.pipe([(12, 5), (12, 8)])
    p.pipe([(13, 5), (13, 7), (24, 7), (24, 8)])

    # Any-ready OR accumulator: arrival order is intentionally irrelevant.
    p.room(11, 18, 18, 5)
    p.text(12, 19, "@0M>R|MR|Mv")
    p.put(22, 20, "<")
    p.put(13, 20, "R")
    p.pipe([(8, 14), (8, 16), (16, 16), (16, 17)])
    p.pipe([(42, 14), (42, 16), (24, 16), (24, 17)])
    return p


def inspect(local, neighbour, tick=200):
    program = build()
    program.save(OUT)
    result = subprocess.run(
        [LM, f"--inspect={tick}", OUT, f"--input={local} {neighbour}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout), program


def main():
    cases = [
        (0x1234, 0x5678000000000000),
        (-1, -(1 << 63)),
        (-0x123456789ABCDEF, 0x7FFF000000000000),
        (0, -1),
    ]
    for local, neighbour in cases:
        snap, program = inspect(local, neighbour)
        assert snap.get("end") != "loaderror", snap
        accumulator = max(snap["runners"], key=lambda runner: runner["id"])
        expected = signed((local << 16) | ((neighbour & MASK64) >> 48))
        assert accumulator["b"] == expected, (local, neighbour, expected, snap)
        print(
            f"PASS local={local} neighbour={neighbour}: "
            f"candidate={expected}"
        )
    print("PASS physical cross-word candidate", program.footprint())


if __name__ == "__main__":
    main()
