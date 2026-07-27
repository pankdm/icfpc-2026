#!/usr/bin/env python3
"""Pack sixteen Pathfinder setup cells into one unsigned row word.

Input cells are 0=open and 1=wall.  The worker keeps the row accumulator in B
and the remaining cell count in BP:

    open: B = 2*B + 1
    wall: B = 2*B

After sixteen inputs it emits the 16-bit OPEN mask, reinitialises BP/B, and
continues with the next row.  The probe checks several rows in one run.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import littleman as lm


LM = os.path.join(ROOT, "interp", "target", "release", "lm")
OUT = "/tmp/pathfinder-setup-row-packer.man"


def build():
    program = lm.Program()
    program.input_room(10, -5)
    program.room(0, 0, 35, 12)

    # Initial BP=16, B=0.
    program.text(1, 2, "@8M+b0M")
    program.put(10, 2, ">")
    program.put(11, 2, "r")
    program.put(12, 2, "X")

    # Open (A=0): B := 2*B+1.
    program.text(13, 2, "WM+M1+M")
    program.put(20, 2, "v")
    program.put(20, 8, ">")

    # Wall (A=1): B := 2*B.
    program.text(12, 3, "0WM+M", d="S")
    program.put(12, 8, ">")

    # Both arms have A=B=new accumulator.  Positive BP turns south and
    # returns to the receive; zero continues east, emits the row, and resets.
    program.put(23, 8, "m")
    program.put(24, 8, "d")
    program.put(25, 8, "s")
    program.text(26, 8, "8M+b0M")
    program.put(32, 8, "v")

    program.put(32, 10, "<")
    program.put(24, 10, "<")
    program.put(10, 10, "^")

    program.pipe([(11, -2), (11, -1)])
    program.output_room(24, -8)
    program.pipe([(25, -1), (25, -5)])
    return program


def mask(row):
    value = 0
    for wall in row:
        value = 2 * value + (1 - wall)
    return value


def main():
    rows = [
        [1] * 16,
        [0] * 16,
        [i & 1 for i in range(16)],
        [1 if i in (0, 3, 7, 15) else 0 for i in range(16)],
    ]
    expected = [mask(row) for row in rows]
    values = [cell for row in rows for cell in row]

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
    print("PASS setup row packer:", expected)
    print("settle:", verdict["settleTick"])
    print("footprint:", program.footprint())


if __name__ == "__main__":
    main()
