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
from pathfinder_packet_stages import packet_stage, perimeter_slots
from pathfinder_parent_query import parent_room
from pathfinder_parent_query_compact import parent_room_compact
from pathfinder_next_demux import next_demux_room_compact
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


def packet_stage_tagged_last(program, x, y):
    """Ordinary D stage that prepends positive mode to its final packet.

    The untagged D stage uses fourteen of sixteen perimeter slots.  Loading
    and sending 1 immediately after @ consumes the two spare slots and emits
    [1,U,R,L,D,state], eliminating all controller-side mode injection.
    """
    h = 9
    right = x + 5
    bottom = y + h - 2
    program.room(x, y, 7, h)
    program.put(x + 1, y + 1, ">")
    program.put(right, y + 1, "v")
    program.put(right, bottom, "<")
    program.put(x + 1, bottom, "^")
    ops = ["@", "1", "s"]
    ops += ["r", "s"] * 3
    ops += ["r", "M", "r", "&", "s", "W", "s"]
    slots = perimeter_slots(x, y, h)
    assert len(ops) == len(slots) == 16
    for position, op in zip(slots, ops):
        program.put(*position, op)


def build(frontiers=None, states=None, layers=64, compact=False):
    pitch = 10 if compact else PITCH
    tile0 = 2 if compact else TILE0
    ctrl_w = 164 if compact else CTRL_W
    parent_builder = parent_room_compact if compact else parent_room
    parent_h = 14 if compact else 18
    program = lm.Program()
    program.room(0, 0, ctrl_w, CTRL_H)

    # Initial mode prefix and row-zero U boundary.
    program.put(1, 1, ">")
    program.put(2, 1, "@")
    if not compact:
        program.text(tile0 - 1, 1, "1s")

    for lane in range(LANES):
        base = tile0 + lane * pitch
        put_lane_path(
            program,
            lane,
            pitch=pitch,
            tile0=tile0,
            # At tile0=2, lane zero's base-1 is x=1: the controller's
            # return corridor.  Row 8's east turn would then skip both seed
            # receives on every later lap.  Lane zero has no previous-row D
            # append, so its default left column is both safe and free.
            d_send_x=None if compact and lane == 0 else base - 1,
        )
        if not compact and lane + 1 < LANES:
            # At lane exit B=current frontier.  Loading/sending 1 changes only
            # A, so B remains the next lane's U candidate.  Put s at the far
            # end of the gap, where the next packet pipe is strictly nearer
            # than the previous one.
            program.text(base + pitch - 1, 1, "1s")

    last_base = tile0 + (LANES - 1) * pitch
    last_exit = last_base + 7
    program.put(last_exit + 1, 1, "0")
    program.put(last_exit + 2, 1, "s")
    right_inner = ctrl_w - 2
    program.put(right_inner, 1, "v")
    program.put(right_inner, 12, "r")
    program.put(right_inner, 13, "X")
    if compact:
        # Zero means layer 64 completed at lane 15, but earlier lanes may
        # still be finishing that sweep.  Drain their final [state,frontier]
        # returns in reverse column order before halting.  Without this
        # barrier lane 0's packet can remain backpressured forever.
        program.put(right_inner, 14, "<")
        for lane in range(LANES - 1, -1, -1):
            base = tile0 + lane * pitch
            program.put(base + 3, 14, "r")
            program.put(base + 2, 14, "r")
        # Lane zero is issued a full sweep before the lane-15 completion
        # signal and can have two packets in flight at shutdown.
        program.put(tile0 + 1, 14, "r")
        program.put(tile0, 14, "r")
        program.put(1, 14, "H")
    else:
        program.put(right_inner, 14, "H")
    program.put(5, 13, "0")
    program.put(4, 13, "M")
    program.put(1, 13, "^")

    merge_y = 20
    stage_y = (34, 46, 58, 70)
    parent_y = (82, 99, 116, 133) if compact else (82, 103, 124, 145)
    next_y = 152 if compact else 166
    counter_x = 146 if compact else 196
    counter_y = 187 if compact else 181

    if frontiers is None:
        frontiers = [(lane % 8) + 1 for lane in range(LANES)]
    if states is None:
        states = [7] * LANES
    assert len(frontiers) == LANES and len(states) == LANES
    assert all(0 <= value <= 9 for value in [*frontiers, *states])

    for lane, frontier in enumerate(frontiers):
        base = tile0 + lane * pitch
        lane_x = base + 3
        packet_col = base + 6
        # base+2 is the persistent NEXT->merge return highway.
        # In the pitch-ten fold, shift the nine-wide parent room one column
        # left.  Otherwise the next lane's NEXT->merge return highway
        # (next_base+1) overwrites this room's right-hand corners.
        parent_x = base + (2 if compact else 3)

        seed_merge_room(program, base, merge_y, states[lane], frontier)
        program.pipe([
            (base + 3, merge_y - 1),
            (base + 3, CTRL_H),
        ])

        for index, y in enumerate(stage_y):
            if compact and index < 3:
                packet_stage(program, lane_x, y, index)
            elif compact:
                packet_stage_tagged_last(program, lane_x, y)
            else:
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
            parent_builder(program, parent_x, y, direction)

        # D stage -> U parent; all parent services have one input and one
        # output, so their physical wall is irrelevant to r/s ownership.
        parent_port_x = parent_x + 4
        program.pipe([
            (lane_x + 2, stage_y[3] + 9),
            # The first segment must leave D's bottom wall vertically.  When
            # parent_y[0]-3 equals the source y, collapsing these two points
            # makes the first glyph point east from empty space: Rust used to
            # accept that orphan endpoint, but the oracle topology parser
            # correctly rejects it.
            (lane_x + 2, parent_y[0] - 2),
            (parent_port_x, parent_y[0] - 2),
            (parent_port_x, parent_y[0] - 1),
        ])
        for direction in range(3):
            y = parent_y[direction]
            dest_y = parent_y[direction + 1]
            program.pipe([
                (parent_port_x, y + parent_h),
                (parent_port_x, dest_y - 1),
            ])

        if compact:
            # Three-way NEXT: ordinary wavefront packets return below,
            # reconstruction replies leave through a second top port, and
            # reset mode zero is consumed.
            next_x = lane_x - 1
            next_demux_room_compact(
                program, next_x, next_y, broadcast_last=lane == LANES - 1
            )
            program.pipe([
                (parent_port_x, parent_y[3] + parent_h),
                (parent_port_x, next_y - 1),
            ])
            # The reconstruction builder will attach NEXT's second output.
            # This closed-wavefront probe exercises only the positive hot
            # path; the negative output is oracle-tested independently.
            return_pipe = [
                (next_x + 3, next_y + 21),
                (next_x + 3, next_y + 23),
                (base + 1, next_y + 23),
            ]
        else:
            # Drop mode, consume U/R/L/D, then return [state, frontier].
            next_ops = ["@", "r", "0", "M"]
            for _ in range(4):
                next_ops += ["r", "|", "M"]
            next_ops += [
                "r", "~", "s", "W", "S" if lane == LANES - 1 else "s"
            ]
            lane_loop_room(program, lane_x, next_y, 12, next_ops)
            program.pipe([
                (parent_port_x, parent_y[3] + parent_h),
                (parent_port_x, next_y - 2),
                (lane_x + 2, next_y - 2),
                (lane_x + 2, next_y - 1),
            ])
            return_pipe = [
                (base + 2, next_y + 5),
                (base + 1, next_y + 5),
            ]
        program.pipe(return_pipe + [
            # Attach beside the lowercase state send.  The old bottom
            # attachment became one cell farther than row 15's trigger after
            # adding the mode-drop op, so state silently selected the trigger.
            (base + 1, merge_y + 8),
            (base + 2, merge_y + 8),
            (base + 2, merge_y + 7),
        ])

        if lane == LANES - 1:
            if compact:
                program.pipe([
                    (next_x + 9, next_y + 17),
                    (next_x + 10, next_y + 17),
                    (next_x + 10, counter_y - 2),
                    (counter_x + 16, counter_y - 2),
                    (counter_x + 16, counter_y - 1),
                ])
            else:
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
        (counter_x + 19, counter_y + 3),
        (ctrl_w + 2, counter_y + 3),
        (ctrl_w + 2, 12),
        (ctrl_w, 12),
    ])
    return program, frontiers, states, parent_y


def inspect(frontiers=None, states=None, tick=100000, layers=64, compact=False):
    program, frontiers, states, parent_y = build(
        frontiers, states, layers=layers, compact=compact
    )
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
        snapshot, program, frontiers, states, parent_y = inspect(
            frontiers, states, compact=True
        )
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
