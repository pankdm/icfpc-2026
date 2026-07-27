#!/usr/bin/env python3
"""Sixteen concurrent four-word Pathfinder parent rings.

Each board row owns a four-word U/R/D/L ring, but the return endpoints share
one room.  A diagonal ``Y`` runway creates sixteen permanent relays in that
room.  The row updater rooms remain separate because each needs one initial
man and two independently selected inputs:

* a broadcast HIT stream enters through the top;
* the next parent word returns through the bottom;
* the updated word is sent back to the shared relay.

The probe broadcasts two layers of four HIT values followed by four zero
updates.  Every lane must finish with the same canonical U/R/D/L words.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import littleman as lm


LM = os.path.join(ROOT, "interp", "target", "release", "lm")
OUT = "/tmp/pathfinder-fork-parent-rings.man"
LANES = 16
PITCH = 9
BASE0 = 1
UPDATER_Y = 10
UPDATER_H = 16
HALL_Y = 31
HALL_H = 8


def updater_room(program, base):
    """Build one four-word ring updater in a seven-column strip."""
    y = UPDATER_Y
    program.room(base, y, 7, UPDATER_H)

    # Seed four zero words.  The sole outgoing pipe is the ring request, so
    # all four lowercase sends have unambiguous ownership.
    program.put(base + 3, y + 4, "@")
    program.put(base + 4, y + 4, "v")
    program.put(base + 4, y + 5, "0")
    for iy in range(y + 6, y + 10):
        program.put(base + 4, iy, "s")
    program.put(base + 4, y + 10, "<")
    program.put(base + 1, y + 10, "^")

    # Persistent lap:
    #   HIT -> B; parent -> A; A |= B; return updated parent.
    # The two receives sit next to different walls and therefore select their
    # intended ports even when the other input is already ready.
    program.put(base + 1, y + 2, "r")
    program.put(base + 1, y + 1, ">")
    program.put(base + 2, y + 1, "M")
    program.put(base + 5, y + 1, "v")
    program.put(base + 5, y + 12, "r")
    program.put(base + 5, y + 13, "|")
    program.put(base + 5, y + 14, "<")
    program.put(base + 4, y + 14, "s")
    program.put(base + 1, y + 14, "^")


def build():
    program = lm.Program()

    # One input token is atomically broadcast to every row updater.
    program.input_room(70, -5)
    program.room(0, 0, 146, 5)
    program.text(68, 1, ">@rSv")
    program.put(72, 2, "<")
    program.put(68, 2, "^")
    program.pipe([(71, -2), (71, -1)])

    # The shared relay hall.  Four binary split levels create sixteen leaf
    # relays while consuming only eight rows.
    program.room(0, HALL_Y, 146, HALL_H)
    program.put(71, HALL_Y + 1, "@")
    program.put(72, HALL_Y + 1, "v")
    program.put(72, HALL_Y + 2, "Y")
    levels = [
        (HALL_Y + 2, (36, 108)),
        (HALL_Y + 3, (18, 54, 90, 126)),
        (HALL_Y + 4, (9, 27, 45, 63, 81, 99, 117, 135)),
    ]
    for row, targets in levels:
        for x in targets:
            program.put(x, row, "v")
            program.put(x, row + 1, "Y")

    for lane in range(LANES):
        base = BASE0 + lane * PITCH

        updater_room(program, base)

        if lane % 2 == 0:
            request_x = base + 4
            response_x = base + 3
            program.put(base + 5, HALL_Y + 5, "<")
            program.put(base + 4, HALL_Y + 5, "r")
            program.put(base + 3, HALL_Y + 5, "s")
            program.put(base + 2, HALL_Y + 5, "v")
            program.put(base + 2, HALL_Y + 6, ">")
            program.put(base + 5, HALL_Y + 6, "^")
        else:
            request_x = base + 2
            response_x = base + 3
            program.put(base + 1, HALL_Y + 5, ">")
            program.put(base + 2, HALL_Y + 5, "r")
            program.put(base + 3, HALL_Y + 5, "s")
            program.put(base + 4, HALL_Y + 5, "v")
            program.put(base + 4, HALL_Y + 6, "<")
            program.put(base + 1, HALL_Y + 6, "^")

        # Broadcast HIT input.
        program.pipe([
            (base + 1, 5),
            (base + 1, UPDATER_Y - 1),
        ])

        # Updated parent descends to the relay; the echo returns beside it.
        program.pipe([
            (request_x, UPDATER_Y + UPDATER_H),
            (request_x, HALL_Y - 1),
        ])
        program.pipe([
            (response_x, HALL_Y - 1),
            (response_x, UPDATER_Y + UPDATER_H),
        ])

    return program


def pipe_values(pipe):
    return [
        item["value"]
        for item in sorted(
            pipe.get("values") or [],
            key=lambda item: -item["index"],
        )
    ]


def main():
    values = [1, 2, 4, 8, 16, 32, 64, 128, 0, 0, 0, 0]
    expected = [17, 34, 68, 136]

    program = build()
    program.save(OUT)
    result = subprocess.run(
        [LM, "--inspect=4000", OUT, f"--input={' '.join(map(str, values))}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    snapshot = json.loads(result.stdout)
    assert snapshot.get("end") not in ("loaderror", "fatal"), snapshot

    returns = {
        pipe["src"][0]: pipe_values(pipe)
        for pipe in snapshot["pipes"]
        if pipe["src"][1] > pipe["dst"][1]
        and pipe["srcRoom"] != 0
    }
    assert len(returns) == LANES, (len(returns), snapshot)
    for lane in range(LANES):
        base = BASE0 + lane * PITCH
        response_x = base + 3
        got = returns[response_x]
        assert got == expected, (lane, got, expected, snapshot)

    print("PASS 16 concurrent forked four-word parent rings")
    print("parents:", expected)
    print("footprint:", program.footprint())


if __name__ == "__main__":
    main()
