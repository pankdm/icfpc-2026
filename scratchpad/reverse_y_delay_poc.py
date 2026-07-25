#!/usr/bin/env python3
"""Minimal Y-fork temporal-stack proof for reverse-a-list.

This is deliberately a fixed-n=3 experiment, not an optimized submission.

The master reads and discards n, then reads three values.  For each value it:

  1. saves the value in B,
  2. loads a worker-specific delay into BP,
  3. restores the value to A, and
  4. executes Y.

The original runner takes Y's clockwise branch and continues as the master.
The clone takes the counter-clockwise branch into a private countdown
racetrack.  The three delays are 5, 3, and 1 laps.  After their private delay,
all workers merge onto one corridor and use the room's single outgoing pipe.

Expected probe:

    input:    3 10 20 30
    output:   30 20 10
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

import littleman as lm


MASTER_Y = 16
MASTER_RETURN_Y = 17
LOOP_Y = 14
LOOP_TOP = 12
MERGE_X = 38
SEND_Y = 16


def build():
    p = lm.Program()
    put = p.put

    # One work room.  It has exactly one incoming pipe and one outgoing pipe.
    p.room(0, 0, 41, 19)

    # Input room on the left.  The first item is n=3 and is discarded.
    p.input_room(-5, 1)
    p.pipe([(-2, 2), (-1, 2)])

    # Output room on the right.  Every worker targets this same outgoing pipe.
    p.output_room(43, SEND_Y - 1)
    p.pipe([(41, SEND_Y), (42, SEND_Y)])

    # Master preamble: discard n, then enter the first fixed worker stage.
    put(1, MASTER_Y, "@")
    put(2, MASTER_Y, "r")

    # Each stage is: r(value), M, delay, b, W, Y.
    # Incoming direction at Y is east:
    #   original -> south, remains the master
    #   clone    -> north, becomes the value worker
    stages = [
        # value-r x, delay, worker merge row
        (3, 5, 9),
        (13, 3, 8),
        (23, 1, 7),
    ]

    for i, (read_x, delay, merge_row) in enumerate(stages):
        yx = read_x + 5
        put(read_x, MASTER_Y, "r")
        put(read_x + 1, MASTER_Y, "M")
        put(read_x + 2, MASTER_Y, str(delay))
        put(read_x + 3, MASTER_Y, "b")
        put(read_x + 4, MASTER_Y, "W")
        put(yx, MASTER_Y, "Y")

        # Clone path and private countdown racetrack.
        #
        # Clone is born at (yx,15), facing north.  It reaches (yx,14), turns
        # east, then repeats:
        #
        #       +---<
        #       v   ^
        #       > m a --exit-->
        #
        # m decrements BP.  a turns north while BP>0; at zero it goes east.
        put(yx, LOOP_Y, ">")
        put(yx + 1, LOOP_Y, "m")
        put(yx + 2, LOOP_Y, "a")
        put(yx + 2, LOOP_TOP, "<")
        put(yx, LOOP_TOP, "v")

        # After exiting the loop, turn north onto a worker-specific horizontal
        # row.  The rows are distinct, so faster later workers can pass the
        # earlier workers without collision.
        route_x = yx + 4
        put(route_x, LOOP_Y, "^")
        put(route_x, merge_row, ">")
        put(MERGE_X, merge_row, "v")

        if i < len(stages) - 1:
            # The original/master is born south of Y.  Route it east and back
            # north into the next stage.
            next_read_x = stages[i + 1][0]
            turn_x = next_read_x - 1
            put(yx, MASTER_RETURN_Y, ">")
            put(turn_x, MASTER_RETURN_Y, "^")
            put(turn_x, MASTER_Y, ">")
        else:
            # The master is disposable after launching the final worker.
            put(yx, MASTER_RETURN_Y, "H")

    # Shared single-file output corridor.  The private delays and route lengths
    # make worker 3 arrive first, then worker 2, then worker 1.
    put(MERGE_X, SEND_Y, "s")
    put(MERGE_X, SEND_Y + 1, "H")

    return p


if __name__ == "__main__":
    program = build()
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "reverse_y_delay_poc.man")
    program.save(out)
    print(program.render())
    print("footprint:", program.footprint())
    print("saved:", out)
