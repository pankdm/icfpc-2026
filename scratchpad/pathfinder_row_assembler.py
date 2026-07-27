#!/usr/bin/env python3
"""Tight row-local packet assembler for a parallel Pathfinder wavefront.

Input per layer:
    [state, U, self_for_R, self_for_L, D]

Output:
    [state, U, 2*self, self//2, D]

A separate ``@rS`` relay broadcasts each row frontier to the adjacent row
assemblers plus the row's two self inputs.  Sixteen copies eliminate the
serial shared-controller sweep.
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "scratchpad"))

import littleman as lm

from pathfinder_closed_wavefront import lane_loop_room


LM = os.path.join(ROOT, "interp", "target", "release", "lm")
OUT = "/tmp/pathfinder-row-assembler.man"


def row_assembler(program, x, y):
    ops = [
        "@",
        "r", "s",                 # state
        "r", "s",                 # U
        "r", "M", "+", "s",       # R = 2*self
        "r", "M", "2", "W", "/", "s",  # L = self//2
        "r", "s",                 # D
    ]
    lane_loop_room(program, x, y, 10, ops)


def build():
    program = lm.Program()
    x, y = 5, 5
    row_assembler(program, x, y)
    program.input_room(0, y)
    program.pipe([(3, y + 1), (x - 1, y + 1)])
    program.output_room(x + 10, y)
    program.pipe([(x + 7, y + 1), (x + 9, y + 1)])
    return program


def main():
    program = build()
    program.save(OUT)
    packets = [
        [65535, 1, 3, 3, 4],
        [42, 16, 17, 17, 32],
        [7, 0, 1, 1, 0],
        [9, 8, 0, 0, 2],
    ]
    inputs = [value for packet in packets for value in packet]
    expected = []
    for state, up, own_r, own_l, down in packets:
        expected += [state, up, 2 * own_r, own_l // 2, down]
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
    print("PASS tight row-local assembler")
    print(result.stdout.strip())
    print("footprint:", program.footprint())


if __name__ == "__main__":
    main()
