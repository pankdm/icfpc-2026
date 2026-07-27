#!/usr/bin/env python3
"""Spawn sixteen independent relays with a four-level binary fork tree.

The earlier diagonal runway needs one row per worker.  Here every south-facing
``Y`` bisects a horizontal interval.  Its children run west/east to the
centres of the two half-intervals, turn south, and split again on the next
row.  Four levels produce sixteen leaf men in an eight-row shared room.

Leaf loops are mirrored.  West-going leaves use ``r s v`` right-to-left;
east-going leaves use it left-to-right.  Sixteen tester rooms prove that each
leaf owns its intended request/response pair.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import littleman as lm


LM = os.path.join(ROOT, "interp", "target", "release", "lm")
OUT = "/tmp/pathfinder-fork-tree-relay-hall.man"
LANES = 16
PITCH = 9
BASE0 = 1
HALL_H = 8
TEST_Y = 13


def build():
    program = lm.Program()
    program.room(0, 0, 146, HALL_H)

    # Root: the initial east-going man turns south into the first split.
    program.put(71, 1, "@")
    program.put(72, 1, "v")
    program.put(72, 2, "Y")

    # Each level's children run to disjoint half-interval centres.  A ``v`` at
    # the target drops the child directly onto the next level's Y.
    levels = [
        (2, (36, 108)),
        (3, (18, 54, 90, 126)),
        (4, (9, 27, 45, 63, 81, 99, 117, 135)),
    ]
    for row, targets in levels:
        for x in targets:
            program.put(x, row, "v")
            program.put(x, row + 1, "Y")

    for lane in range(LANES):
        base = BASE0 + lane * PITCH
        west_leaf = lane % 2 == 0

        if west_leaf:
            # The leaf arrives heading west.
            request_x = base + 4
            response_x = base + 3
            program.put(base + 5, 5, "<")
            program.put(base + 4, 5, "r")
            program.put(base + 3, 5, "s")
            program.put(base + 2, 5, "v")
            program.put(base + 2, 6, ">")
            program.put(base + 5, 6, "^")
        else:
            # The leaf arrives heading east.
            request_x = base + 2
            response_x = base + 3
            program.put(base + 1, 5, ">")
            program.put(base + 2, 5, "r")
            program.put(base + 3, 5, "s")
            program.put(base + 4, 5, "v")
            program.put(base + 4, 6, "<")
            program.put(base + 1, 6, "^")

        program.room(base, TEST_Y, 7, 5)
        program.text(base + 1, TEST_Y + 1, "@7srr")

        # Tester request travels up; relay response travels down.
        program.pipe([
            (request_x, TEST_Y - 1),
            (request_x, HALL_H),
        ])
        program.pipe([
            (response_x, HALL_H),
            (response_x, TEST_Y - 1),
        ])

    return program


def main():
    program = build()
    program.save(OUT)
    result = subprocess.run(
        [LM, "--inspect=1000", OUT],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    snapshot = json.loads(result.stdout)
    assert snapshot.get("end") not in ("loaderror", "fatal"), snapshot

    testers = [
        runner
        for runner in snapshot["runners"]
        if TEST_Y < runner["pos"][1] < TEST_Y + 4
    ]
    relays = [
        runner
        for runner in snapshot["runners"]
        if runner["pos"][1] in (5, 6)
    ]
    assert len(testers) == LANES, (len(testers), snapshot)
    assert len(relays) == LANES, (len(relays), snapshot)
    assert not any(runner["halted"] for runner in relays), relays
    assert all(runner["a"] == 7 for runner in testers), testers

    print("PASS binary-fork shared relay hall: 16/16")
    print("footprint:", program.footprint())


if __name__ == "__main__":
    main()
