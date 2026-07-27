#!/usr/bin/env python3
"""Persistent 16-row streaming Pathfinder wavefront.

This closes the previously composed driver and priority bands:

    seed/return merge -> streaming driver -> U/R/L/D packet stages
    -> parent accumulator -> NEXT -> seed/return merge

Every lane returns ``[state,frontier]``.  The controller's next lap is the
global barrier: it blocks on the first late row rather than using a timer.
Fixed small seed words keep this probe focused on persistent protocol and
physical routing; board setup and the four-word parent ring remain separate.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "scratchpad"))

import littleman as lm

from pathfinder_packet_stages import packet_stage
from pathfinder_stream_driver import (
    CTRL_H,
    CTRL_W,
    LANES,
    LM,
    PITCH,
    TILE0,
    put_lane_path,
)


OUT = "/tmp/pathfinder-closed-wavefront.man"


def lane_loop_room(p, x, y, h, ops):
    """Width-seven clockwise room using the packet-stage perimeter."""
    p.room(x, y, 7, h)
    right = x + 5
    bottom = y + h - 2
    p.put(x + 1, y + 1, ">")
    p.put(right, y + 1, "v")
    p.put(right, bottom, "<")
    p.put(x + 1, bottom, "^")
    slots = []
    slots.extend((cx, y + 1) for cx in range(x + 2, right))
    slots.extend((right, cy) for cy in range(y + 2, bottom))
    slots.extend((cx, bottom) for cx in range(right - 1, x + 1, -1))
    slots.extend((x + 1, cy) for cy in range(bottom - 1, y + 1, -1))
    assert len(ops) <= len(slots), (len(ops), len(slots))
    for pos, op in zip(slots, ops):
        p.put(*pos, op)


def seed_merge_room(p, x, y, state, frontier):
    """Send one seed pair, then remain in a lower R->s return loop."""
    p.room(x, y, 7, 7)

    # One-time top path.
    p.put(x + 1, y + 1, "@")
    p.put(x + 2, y + 1, str(state))
    p.put(x + 3, y + 1, "s")
    p.put(x + 4, y + 1, str(frontier))
    p.put(x + 5, y + 1, "v")
    p.put(x + 5, y + 2, "s")

    # Persistent lower loop. Initial execution enters at the right and bypasses
    # R/s; later laps approach them from the left.
    p.put(x + 1, y + 3, ">")
    p.put(x + 3, y + 3, "R")
    p.put(x + 4, y + 3, "s")
    p.put(x + 5, y + 3, "v")
    p.put(x + 5, y + 5, "<")
    p.put(x + 1, y + 5, "^")


def build(frontiers=None, states=None):
    p = lm.Program()
    p.room(0, 0, CTRL_W, CTRL_H)
    p.put(1, 1, ">")
    p.put(2, 1, "@")
    for lane in range(LANES):
        put_lane_path(p, lane)

    last_base = TILE0 + (LANES - 1) * PITCH
    last_exit = last_base + 7
    p.put(last_exit + 1, 1, "0")
    p.put(last_exit + 2, 1, "s")
    p.put(147, 1, "v")
    p.put(147, 2, "M")
    p.put(147, 14, "<")
    p.put(1, 14, "^")

    merge_y = 20
    stage_y = (34, 46, 58, 70)
    parent_y = 82
    next_y = 96
    if frontiers is None:
        frontiers = [(lane % 8) + 1 for lane in range(LANES)]
    if states is None:
        states = [7] * LANES
    assert len(frontiers) == LANES and len(states) == LANES
    assert all(0 <= value <= 9 for value in [*frontiers, *states])

    for lane, frontier in enumerate(frontiers):
        base = TILE0 + lane * PITCH
        lane_x = base + 3
        return_col = base + 1
        packet_col = base + 6

        seed_merge_room(p, base, merge_y, states[lane], frontier)

        # The merge's sole output feeds the controller.
        p.pipe([
            (base + 3, merge_y - 1),
            (base + 3, CTRL_H),
        ])

        for index, y in enumerate(stage_y):
            packet_stage(p, lane_x, y, index)

        # Controller packet -> U, detouring through the two-column gap around
        # the seed/merge room.
        p.pipe([
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
            p.pipe([
                (lane_x + 2, y + 9),
                (lane_x + 2, y + 10),
                (lane_x + 5, y + 10),
                (lane_x + 5, dest_y - 1),
            ])

        # Persistent parent summary for the closure probe. It forwards all
        # five words, accumulating only the four TAKE values in B.
        parent_ops = ["@"]
        for _ in range(4):
            parent_ops += ["r", "s", "|", "M"]
        parent_ops += ["r", "s"]
        lane_loop_room(p, lane_x, parent_y, 11, parent_ops)
        p.pipe([
            (lane_x + 2, stage_y[3] + 9),
            (lane_x + 2, parent_y - 1),
        ])

        # NEXT consumes U/R/L/D, then returns [state, frontier].
        next_ops = ["@", "0", "M"]
        for _ in range(4):
            next_ops += ["r", "|", "M"]
        next_ops += ["r", "s", "W", "s"]
        lane_loop_room(p, lane_x, next_y, 12, next_ops)
        p.pipe([
            (lane_x + 2, parent_y + 11),
            (lane_x + 2, next_y - 1),
        ])

        # NEXT -> merge through the left two-column service channel.
        p.pipe([
            (lane_x + 5, next_y + 12),
            (lane_x + 5, next_y + 13),
            (base + 2, next_y + 13),
            (base + 2, merge_y + 7),
        ])

    return p, frontiers, states, parent_y


def reference(frontiers, states, limit=100):
    parents = [0] * LANES
    for _ in range(limit):
        next_frontiers = []
        next_states = []
        for lane in range(LANES):
            candidates = [
                frontiers[lane - 1] if lane else 0,
                2 * frontiers[lane],
                frontiers[lane] // 2,
                frontiers[lane + 1] if lane + 1 < LANES else 0,
            ]
            remaining = states[lane]
            nxt = 0
            for candidate in candidates:
                take = remaining & candidate
                remaining ^= take
                parents[lane] |= take
                nxt |= take
            next_states.append(remaining)
            next_frontiers.append(nxt)
        states = next_states
        frontiers = next_frontiers
        if not any(frontiers):
            return states, parents
    raise AssertionError("reference did not settle")


def inspect(frontiers=None, states=None, tick=5000):
    program, frontiers, states, parent_y = build(frontiers, states)
    program.save(OUT)
    result = subprocess.run(
        [LM, f"--inspect={tick}", OUT],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return (
        json.loads(result.stdout),
        program,
        frontiers,
        states,
        parent_y,
    )


def main():
    cases = [
        (
            [(lane % 8) + 1 for lane in range(LANES)],
            [7] * LANES,
        ),
        (
            [0, 1] * 8,
            [lane % 8 for lane in range(LANES)],
        ),
        (
            [9 - (lane % 9) for lane in range(LANES)],
            [(3 * lane + 1) % 10 for lane in range(LANES)],
        ),
        (
            [1 if lane in (1, 7, 14) else 0 for lane in range(LANES)],
            [9 if lane % 3 else 5 for lane in range(LANES)],
        ),
    ]

    last_program = None
    for case_index, (frontiers, states) in enumerate(cases):
        snapshot, program, frontiers, states, parent_y = inspect(
            frontiers,
            states,
        )
        last_program = program
        assert snapshot.get("end") not in ("loaderror", "fatal"), snapshot

        expected_states, expected_parents = reference(
            frontiers[:],
            states[:],
        )
        parent_runners = sorted(
            (
                runner
                for runner in snapshot["runners"]
                if runner["pos"][1] in range(parent_y + 1, parent_y + 10)
            ),
            key=lambda runner: runner["pos"][0],
        )
        assert len(parent_runners) == LANES, len(parent_runners)
        for lane, runner in enumerate(parent_runners):
            assert runner["b"] == expected_parents[lane], (
                case_index,
                lane,
                runner,
                expected_parents,
                expected_states,
                snapshot,
            )

    print(f"PASS persistent closed 16-row wavefront ({len(cases)} seeds)")
    print("footprint:", last_program.footprint())


if __name__ == "__main__":
    main()
