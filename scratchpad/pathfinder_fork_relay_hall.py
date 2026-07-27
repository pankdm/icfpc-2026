#!/usr/bin/env python3
"""Spawn sixteen independent Pathfinder row relays in one shared room.

The unsigned-row backend wants one tiny parent-ring relay per board row.  A
normal layout needs sixteen rooms because a room may contain only one initial
``@``.  This probe replaces those room walls with a one-time ``Y`` runway:

* an east-heading spawner forks once per column;
* the north copy turns east and continues to the next, one row higher;
* the south copy falls into that column's permanent ``r -> s`` loop;
* the final north copy halts.

Each relay has its own bottom-wall input/output pair.  Sixteen tester rooms
send a 7, receive it back, park with B=7, and thereby prove both population
and nearest-port ownership.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import littleman as lm


LM = os.path.join(ROOT, "interp", "target", "release", "lm")
OUT = "/tmp/pathfinder-fork-relay-hall.man"
LANES = 16
PITCH = 9
X0 = 4
HALL_BOTTOM = 24
TEST_Y = 32


def build():
    program = lm.Program()
    hall_width = X0 + (LANES - 1) * PITCH + 7
    program.room(0, 0, hall_width, HALL_BOTTOM + 1)

    # The only initial man walks east.  Every split's north copy climbs one
    # row and resumes east; its south copy falls toward the relay loop.
    spawn_y = 17
    program.put(1, spawn_y, "@")
    for lane in range(LANES):
        x = X0 + lane * PITCH
        y = spawn_y - lane
        program.put(x, y, "Y")
        if lane + 1 < LANES:
            program.put(x, y - 1, ">")
        else:
            program.put(x, y - 1, "H")

        # The south child reaches this compact eight-tick relay lap:
        #   > r s v
        #   ^   < <
        program.put(x, 20, ">")
        program.put(x + 1, 20, "r")
        program.put(x + 2, 20, "s")
        program.put(x + 3, 20, "v")
        program.put(x + 3, 21, "<")
        program.put(x, 21, "^")

        # One tester room per lane.  It sends 7, receives the echo, stores it
        # in B, and parks forever on a second receive.
        program.room(x - 1, TEST_Y, 8, 5)
        program.text(x, TEST_Y + 1, "@7srMr")

        # Tester -> relay and relay -> tester use adjacent straight columns.
        program.pipe([
            (x + 1, TEST_Y - 1),
            (x + 1, HALL_BOTTOM + 1),
        ])
        program.pipe([
            (x + 2, HALL_BOTTOM + 1),
            (x + 2, TEST_Y - 1),
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
        if runner["pos"][1] in (20, 21)
    ]
    assert len(testers) == LANES, (len(testers), snapshot)
    assert len(relays) == LANES, (len(relays), snapshot)
    assert all(runner["b"] == 7 for runner in testers), testers

    print("PASS forked shared relay hall: 16/16")
    print("footprint:", program.footprint())


if __name__ == "__main__":
    main()
