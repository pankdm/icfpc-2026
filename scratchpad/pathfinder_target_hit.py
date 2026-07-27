#!/usr/bin/env python3
"""Persistent row-target mask and early-stop hit test for Pathfinder.

Protocol:
  [1, mask]         replace the row's target mask
  [-1, frontier]    emit mask & frontier
  [0]               clear the mask

Only one row has a non-zero target mask in a round.  Sixteen copies can test
the newly produced frontiers concurrently and feed a sweep-barrier latch.
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import littleman as lm


LM = os.path.join(ROOT, "interp", "target", "release", "lm")
OUT = "/tmp/pathfinder-target-hit.man"


def target_hit_room(program, x, y):
    width, height = 9, 10
    branch_x = x + 5
    mid = y + 4
    bottom = y + height - 2
    reset_row = mid + 2
    program.room(x, y, width, height)

    program.put(x + 1, mid, ">")
    program.put(x + 2, mid, "@")
    program.put(x + 3, mid, "r")
    program.put(branch_x, mid, "X")

    # Positive update.
    program.put(branch_x, mid + 1, "r")
    program.put(branch_x, mid + 2, "M")
    program.put(branch_x, bottom, "<")
    program.put(x + 1, bottom, "^")

    # Negative test.
    program.put(branch_x, mid - 1, "r")
    program.put(branch_x, mid - 2, "&")
    program.put(branch_x, y + 1, "<")
    program.put(branch_x - 1, y + 1, "s")
    program.put(x + 1, y + 1, "v")

    # Zero clear.  X guarantees A=0, so M clears persistent B.
    program.put(branch_x + 1, mid, "M")
    program.put(branch_x + 2, mid, "v")
    program.put(branch_x + 2, reset_row, "<")
    program.put(x + 1, reset_row, "^")


def build():
    program = lm.Program()
    x, y = 5, 5
    target_hit_room(program, x, y)
    mid = y + 4
    program.input_room(0, mid - 1)
    program.pipe([(3, mid), (x - 1, mid)])
    program.output_room(x + 3, 0)
    program.pipe([(x + 4, y - 1), (x + 4, 3)])
    return program


def main():
    program = build()
    program.save(OUT)
    inputs = [
        1, 32,
        -1, 16,
        -1, 32,
        -1, 48,
        1, 4,
        -1, 36,
        0,
        -1, 63,
    ]
    expected = [0, 32, 32, 4, 0]
    result = subprocess.run(
        [
            LM,
            "--grade",
            OUT,
            "--cap=10000",
            "--input=" + " ".join(map(str, inputs)),
            "--expected=" + " ".join(map(str, expected)),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert '"status":"pass"' in result.stdout, result.stdout
    print("PASS persistent target hit service")
    print("footprint:", program.footprint())


if __name__ == "__main__":
    main()
