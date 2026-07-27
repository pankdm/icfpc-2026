#!/usr/bin/env python3
"""Streaming 16-row Pathfinder packet driver.

Each row return pipe contains ``[state, frontier]``.  One controller man sweeps
left-to-right through nine-column meanders:

* state is sent to the current packet;
* frontier is appended as D to the previous packet;
* the previous frontier is sent as U to the current packet;
* ``2*frontier`` and ``frontier//2`` are sent as R and L;
* the current frontier is recovered exactly and retained in B for the next row.

The result is one ``[state,U,R,L,D]`` packet per row with no frontier RAM.
The send sites are deliberately placed near either the left or right packet
port, proving the nearest-pipe geometry needed by the compact solver.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import littleman as lm


OUT = "/tmp/pathfinder-stream-driver.man"
LM = os.path.join(ROOT, "interp", "target", "release", "lm")
LANES = 16
PITCH = 9
TILE0 = 2
CTRL_W = 149
CTRL_H = 16


def put_lane_path(p, lane, pitch=PITCH, tile0=TILE0, d_send_x=None):
    base = tile0 + lane * pitch
    left = base + 1
    right = base + 6
    exit_col = base + 7

    # Entry from the shared top corridor.
    p.put(left, 1, "v")

    # Receive state near the row-return port, then cross to the current
    # packet port before sending it.
    p.put(left, 2, "r")
    p.put(left, 4, ">")
    p.put(right - 1, 4, "s")
    p.put(right, 4, "v")

    # Return west, consume frontier, and append it as D to the previous row.
    p.put(right, 6, "<")
    p.put(left + 1, 6, "r")
    dcol = left if d_send_x is None else d_send_x
    p.put(dcol, 6, "v")
    if lane:
        p.put(dcol, 7, "s")
    p.put(dcol, 8, ">")

    # A=frontier, B=previous frontier.  Send U, then 2*frontier as R.
    p.put(left + 1, 8, "W")
    p.put(left + 2, 8, "s")
    p.put(left + 3, 8, "W")
    p.put(left + 4, 8, "M")
    p.put(right, 8, "v")
    p.put(right, 9, "+")
    p.put(right, 10, "<")
    p.put(right - 1, 10, "s")

    # Divide by two, send L, then recover the exact original value from
    # quotient and remainder: current = 2*q + remainder.
    p.put(right - 2, 10, "W")
    p.put(right - 3, 10, "M")
    p.put(right - 4, 10, "2")
    p.put(left, 10, "v")
    p.put(left, 11, "W")
    p.put(left, 12, ">")
    p.put(left + 1, 12, "/")
    p.put(right - 1, 12, "s")
    p.put(exit_col, 12, "^")
    p.put(exit_col, 11, "W")
    p.put(exit_col, 10, "+")
    p.put(exit_col, 9, "+")
    p.put(exit_col, 8, "M")
    p.put(exit_col, 1, ">")


def source_room(p, lane, state, frontier):
    """Queue one [state, frontier] pair below the controller."""
    base = TILE0 + lane * PITCH
    x = base
    y = 20
    p.room(x, y, 5, 7)
    p.put(x + 1, y + 1, "@")
    p.put(x + 2, y + 1, str(state))
    p.put(x + 3, y + 1, "v")
    p.put(x + 3, y + 2, "s")
    p.put(x + 3, y + 3, str(frontier))
    p.put(x + 3, y + 4, "s")
    p.put(x + 3, y + 5, "<")
    p.put(x + 2, y + 5, "H")


def build(with_sinks=True):
    p = lm.Program()
    p.room(0, 0, CTRL_W, CTRL_H)

    # Shared cyclic controller path. B starts at zero, the correct U boundary
    # candidate for row zero.
    p.put(1, 1, ">")
    p.put(2, 1, "@")
    for lane in range(LANES):
        put_lane_path(p, lane)

    last_base = TILE0 + (LANES - 1) * PITCH
    last_packet = last_base + 6
    last_exit = last_base + 7

    # Append the zero D boundary to row 15, then return around the unused
    # bottom corridor for another fully data-driven sweep.
    p.put(last_exit + 1, 1, "0")
    p.put(last_exit + 2, 1, "s")
    p.put(147, 1, "v")
    p.put(147, 2, "M")
    p.put(147, 14, "<")
    p.put(1, 14, "^")

    frontiers = [(lane % 8) + 1 for lane in range(LANES)]
    state = 7
    for lane, frontier in enumerate(frontiers):
        base = TILE0 + lane * PITCH
        return_col = base + 1
        packet_col = base + 6

        source_room(p, lane, state, frontier)
        p.pipe([
            (return_col, 19),
            (return_col, 16),
        ])

        if with_sinks:
            # Passive packet sink. Five values fit in the short direct pipe
            # plus the room endpoint without a consumer schedule.
            p.room(packet_col - 1, 29, 3, 3)
            p.pipe([
                (packet_col, 16),
                (packet_col, 28),
            ])

    return p, frontiers, state


def inspect(tick=2000):
    program, frontiers, state = build()
    program.save(OUT)
    result = subprocess.run(
        [LM, f"--inspect={tick}", OUT],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout), program, frontiers, state


def pipe_values(pipe):
    return [
        item["value"]
        for item in sorted(pipe.get("values") or [], key=lambda item: -item["index"])
    ]


def main():
    snapshot, program, frontiers, state = inspect()
    assert snapshot.get("end") not in ("loaderror", "fatal"), snapshot

    packets = sorted(
        (
            pipe
            for pipe in snapshot["pipes"]
            if pipe["dst"][1] == 28
        ),
        key=lambda pipe: pipe["dst"][0],
    )
    assert len(packets) == LANES, len(packets)
    for lane, pipe in enumerate(packets):
        expected = [
            state,
            frontiers[lane - 1] if lane else 0,
            2 * frontiers[lane],
            frontiers[lane] // 2,
            frontiers[lane + 1] if lane + 1 < LANES else 0,
        ]
        got = pipe_values(pipe)
        assert got == expected, (lane, got, expected, snapshot)

    print("PASS streaming [state,U,R,L,D] packets")
    print("footprint:", program.footprint())


if __name__ == "__main__":
    main()
