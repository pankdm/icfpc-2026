#!/usr/bin/env python3
"""Compact Y-fork temporal-stack proof for reverse-a-list.

One master repeatedly returns to the SAME Y cell.  Every visit forks one
value-carrying worker.  Workers share one racetrack and one output pipe:

* clone i inherits A=value_i and BP=n-i-1;
* BP controls how many laps it makes before leaving the track;
* the loop period is deliberately longer than the master's fork period, so
  later values leave first;
* the 34-tick loop and 20-tick fork cadence repeat only after 17 workers, so
  the at-most-15 active clones never occupy the same racetrack cell.
  workers never occupy the same racetrack cell.

This is still a proof artifact, but it has no 16-way unrolled control path and
no private worker loops.  It supports n=1..16 and multiple rounds with one I
pipe and exactly one O pipe.
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "tools"))

import littleman as lm


# One master iteration is 20 ticks from Y to Y.  The worker lap is 34 ticks:
# later worker exits are therefore 14 ticks earlier than their predecessors.
MASTER_Y = 16
MASTER_DEC_Y = 17
MASTER_TEST_Y = 18
MASTER_RETURN_Y = 19
RETURN_RAIL_Y = 22

WORKER_Y = 14
WORKER_TOP_Y = 1
FORK_X = 7
WORKER_LEFT_X = 5
WORKER_A_X = 9
SEND_X = 10

ROOM_RIGHT = 16
ROOM_BOTTOM = 24


def build():
    p = lm.Program()
    put = p.put

    p.room(0, 0, ROOM_RIGHT + 1, ROOM_BOTTOM + 1)

    # The only incoming and outgoing pipes.
    p.input_room(-5, MASTER_Y - 1)
    p.pipe([(-2, MASTER_Y), (-1, MASTER_Y)])
    p.output_room(ROOM_RIGHT + 3, WORKER_Y - 1)
    p.pipe([(ROOM_RIGHT + 1, WORKER_Y), (ROOM_RIGHT + 2, WORKER_Y)])

    # Setup and round re-entry. `r,b` saves n in BP.  The first value takes a
    # short path to the shared r below; later values arrive there from Y.
    put(1, MASTER_Y, ">")
    put(2, MASTER_Y, "@")
    put(3, MASTER_Y, "r")
    put(4, MASTER_Y, "b")
    put(5, MASTER_Y, "v")
    put(5, MASTER_DEC_Y, ">")

    # Repeating master cycle:
    #
    #   r,m,a:    consume a value and make BP one smaller
    #   a>0:      route to Y, creating a worker with the remaining count
    #   a==0:     this was the final value; send it directly and return home
    #   Y:         original returns to r; clone goes north to worker loop
    #
    # No worker reads from I, so the sole r assigns values in input order.
    put(FORK_X, MASTER_Y, "Y")
    put(FORK_X, MASTER_DEC_Y, ">")
    put(9, MASTER_DEC_Y, "v")
    put(9, MASTER_TEST_Y, "r")
    put(9, MASTER_RETURN_Y, "m")
    put(9, MASTER_RETURN_Y + 1, "a")

    # BP>0 branch from a: climb around to approach Y from its west side.
    put(11, MASTER_RETURN_Y + 1, "^")
    put(11, WORKER_Y + 1, "<")
    put(6, WORKER_Y + 1, "v")
    put(6, MASTER_Y, ">")

    # BP==0 leaves a southbound.  It sends the final (most recent) value
    # directly, then returns to the count read while workers drain behind it.
    put(9, MASTER_RETURN_Y + 2, ">")
    put(10, MASTER_RETURN_Y + 2, "s")
    put(11, MASTER_RETURN_Y + 2, "v")
    for x in range(2, 12):
        put(x, RETURN_RAIL_Y, "<")
    put(1, RETURN_RAIL_Y, "^")
    for y in range(MASTER_Y + 1, RETURN_RAIL_Y):
        put(1, y, "^")

    # Shared worker racetrack.  A clone appears at (FORK_X, MASTER_Y-1)
    # facing north, reaches a from the west. `a` exits east at BP=0; otherwise
    # it turns north around the rectangle.  m is on the top leg, so a worker
    # with BP=k takes exactly k laps. Its exact a-to-a period is 34 ticks.
    put(FORK_X, WORKER_Y, ">")
    put(WORKER_A_X, WORKER_Y, "a")
    put(WORKER_A_X, WORKER_TOP_Y, "<")
    put(7, WORKER_TOP_Y, "m")
    put(WORKER_LEFT_X, WORKER_TOP_Y, "v")
    put(WORKER_LEFT_X, WORKER_Y, ">")

    # Single output instruction.  A worker whose BP just reached zero leaves
    # a eastbound and lands here with its original input value still in A.
    put(SEND_X, WORKER_Y, "s")
    put(SEND_X + 1, WORKER_Y, "H")

    return p


if __name__ == "__main__":
    program = build()
    output = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "y-delay-poc.man")
    program.save(output)
    print(program.render())
    print("footprint:", program.footprint())
    print("saved:", output)
