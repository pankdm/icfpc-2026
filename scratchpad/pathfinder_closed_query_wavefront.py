#!/usr/bin/env python3
"""Closed 16-row wavefront with queryable/resettable row-local parents.

This is the correctness-first composition of the raw Pathfinder core.  It
widens lane pitch from nine to twelve so each row can use the proven spacious
10x18 parent service from ``pathfinder_parent_query.py``.  The hot packet is:

    [1, state, U, R, L, D]

Priority stages preserve the positive mode token, parent rooms consume it to
select their update lap, and NEXT drops it before computing the new frontier.
The fixed 64-layer gate is unchanged.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "scratchpad"))

import littleman as lm

from pathfinder_closed_wavefront import (
    lane_loop_room,
    reference,
    seed_merge_room,
)
from pathfinder_packet_stages import perimeter_slots
from pathfinder_parent_query import parent_room
from pathfinder_stream_driver import LM, put_lane_path


OUT = "/tmp/pathfinder-closed-query-wavefront.man"
LANES = 16
PITCH = 13
TILE0 = 7
CTRL_W = 216
CTRL_H = 16


def packet_stage_mode(program, x, y, index):
    """Priority stage preserving a leading positive mode token."""
    h = 9
    right = x + 5
    bottom = y + h - 2
    program.room(x, y, 7, h)
    program.put(x + 1, y + 1, ">")
    program.put(right, y + 1, "v")
    program.put(right, bottom, "<")
    program.put(x + 1, bottom, "^")

    ops = ["@", "r", "s"]
    ops += ["r", "s"] * index
    ops += ["r", "M", "r", "&", "s", "W", "s"]
    ops += ["r", "s"] * (3 - index)
    slots = perimeter_slots(x, y, h)
    assert len(ops) == 16 and len(ops) <= len(slots)
    for position, op in zip(slots, ops):
        program.put(*position, op)


def build(frontiers=None, states=None, layers=64):
    program = lm.Program()
    program.room(0, 0, CTRL_W, CTRL_H)

    # Initial mode prefix and row-zero U boundary.
    program.put(1, 1, ">")
    program.put(2, 1, "@")
    program.text(6, 1, "1s")

    for lane in range(LANES):
        base = TILE0 + lane * PITCH
        put_lane_path(
            program,
            lane,
            pitch=PITCH,
            tile0=TILE0,
            d_send_x=base - 1,
        )
        if lane + 1 < LANES:
            # At lane exit B=current frontier.  Loading/sending 1 changes only
            # A, so B remains the next lane's U candidate.  Put s at the far
            # end of the gap, where the next packet pipe is strictly nearer
            # than the previous one.
            program.text(base + 12, 1, "1s")

    last_base = TILE0 + (LANES - 1) * PITCH
    last_exit = last_base + 7
    program.put(last_exit + 1, 1, "0")
    program.put(last_exit + 2, 1, "s")
    program.put(214, 1, "v")
    program.put(214, 12, "r")
    program.put(214, 13, "X")
    program.put(214, 14, "H")
    program.put(5, 13, "0")
    program.put(4, 13, "M")
    program.put(1, 13, "^")

    merge_y = 20
    stage_y = (34, 46, 58, 70)
    parent_y = (82, 103, 124, 145)
    next_y = 166
    counter_x = 196
    counter_y = 181

    if frontiers is None:
        frontiers = [(lane % 8) + 1 for lane in range(LANES)]
    if states is None:
        states = [7] * LANES
    assert len(frontiers) == LANES and len(states) == LANES
    assert all(0 <= value <= 9 for value in [*frontiers, *states])

    for lane, frontier in enumerate(frontiers):
        base = TILE0 + lane * PITCH
        lane_x = base + 3
        packet_col = base + 6
        # base+2 is the persistent NEXT->merge return highway.
        parent_x = base + 3

        seed_merge_room(program, base, merge_y, states[lane], frontier)
        program.pipe([
            (base + 3, merge_y - 1),
            (base + 3, CTRL_H),
        ])

        for index, y in enumerate(stage_y):
            packet_stage_mode(program, lane_x, y, index)

        program.pipe([
            (packet_col, CTRL_H),
            (packet_col, 18),
            (base + 8, 18),
            (base + 8, stage_y[0] - 2),
            (packet_col, stage_y[0] - 2),
            (packet_col, stage_y[0] - 1),
        ])
        for index in range(3):
            y = stage_y[index]
            dest_y = stage_y[index + 1]
            program.pipe([
                (lane_x + 2, y + 9),
                (lane_x + 2, y + 10),
                (lane_x + 5, y + 10),
                (lane_x + 5, dest_y - 1),
            ])

        for direction, y in enumerate(parent_y):
            parent_room(program, parent_x, y, direction)

        # D stage -> U parent; all parent services have one input and one
        # output, so their physical wall is irrelevant to r/s ownership.
        parent_port_x = parent_x + 4
        program.pipe([
            (lane_x + 2, stage_y[3] + 9),
            (lane_x + 2, parent_y[0] - 3),
            (parent_port_x, parent_y[0] - 3),
            (parent_port_x, parent_y[0] - 1),
        ])
        for direction in range(3):
            y = parent_y[direction]
            dest_y = parent_y[direction + 1]
            program.pipe([
                (parent_port_x, y + 18),
                (parent_port_x, dest_y - 1),
            ])

        # Drop mode, consume U/R/L/D, then return [state, frontier].
        next_ops = ["@", "r", "0", "M"]
        for _ in range(4):
            next_ops += ["r", "|", "M"]
        next_ops += ["r", "~", "s", "W", "S" if lane == LANES - 1 else "s"]
        lane_loop_room(program, lane_x, next_y, 12, next_ops)
        program.pipe([
            (parent_port_x, parent_y[3] + 18),
            (parent_port_x, next_y - 2),
            (lane_x + 2, next_y - 2),
            (lane_x + 2, next_y - 1),
        ])
        program.pipe([
            # Attach beside the lowercase state send.  The old bottom
            # attachment became one cell farther than row 15's trigger after
            # adding the mode-drop op, so state silently selected the trigger.
            (base + 2, next_y + 5),
            (base + 1, next_y + 5),
            (base + 1, merge_y + 8),
            (base + 2, merge_y + 8),
            (base + 2, merge_y + 7),
        ])

        if lane == LANES - 1:
            program.pipe([
                (lane_x + 7, next_y + 1),
                (lane_x + 8, next_y + 1),
                (lane_x + 8, next_y + 3),
                (lane_x + 7, next_y + 3),
                (lane_x + 7, counter_y - 1),
            ])

    program.room(counter_x, counter_y, 19, 7)
    assert layers == 64 or 1 <= layers <= 9
    if layers == 64:
        program.text(counter_x + 1, counter_y + 1, "@8M*bv")
    else:
        program.put(counter_x + 1, counter_y + 1, "@")
        program.put(counter_x + 2, counter_y + 1, str(layers))
        program.put(counter_x + 3, counter_y + 1, "b")
        program.put(counter_x + 6, counter_y + 1, "v")
    program.text(counter_x + 6, counter_y + 3, ">rmd0sH")
    program.put(counter_x + 9, counter_y + 4, ">")
    program.text(counter_x + 10, counter_y + 4, "1s")
    program.put(counter_x + 17, counter_y + 4, "^")
    program.put(counter_x + 17, counter_y + 2, "<")
    program.put(counter_x + 6, counter_y + 2, "v")

    program.pipe([
        (215, counter_y + 3),
        (217, counter_y + 3),
        (217, 12),
        (216, 12),
    ])
    return program, frontiers, states, parent_y


def inspect(frontiers=None, states=None, tick=100000, layers=64):
    program, frontiers, states, parent_y = build(frontiers, states, layers=layers)
    program.save(OUT)
    result = subprocess.run(
        [LM, f"--inspect={tick}", OUT],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout), program, frontiers, states, parent_y


def main():
    cases = [
        (
            [(lane % 8) + 1 for lane in range(LANES)],
            [7] * LANES,
        ),
        (
            [1 if lane in (1, 7, 14) else 0 for lane in range(LANES)],
            [9 if lane % 3 else 5 for lane in range(LANES)],
        ),
    ]
    last_program = None
    for case_index, (frontiers, states) in enumerate(cases):
        snapshot, program, frontiers, states, parent_y = inspect(frontiers, states)
        last_program = program
        assert snapshot.get("end") not in ("loaderror", "fatal"), snapshot
        expected_states, expected_parents = reference(frontiers[:], states[:])
        for direction, y in enumerate(parent_y):
            runners = sorted(
                (
                    runner for runner in snapshot["runners"]
                    if y < runner["pos"][1] < y + 17
                ),
                key=lambda runner: runner["pos"][0],
            )
            assert len(runners) == LANES, (direction, len(runners), snapshot)
            for lane, runner in enumerate(runners):
                assert runner["b"] == expected_parents[direction][lane], (
                    case_index,
                    direction,
                    lane,
                    runner,
                    expected_parents,
                    expected_states,
                )
    print(f"PASS closed queryable wavefront ({len(cases)} seeds)")
    print("footprint:", last_program.footprint())


if __name__ == "__main__":
    main()
