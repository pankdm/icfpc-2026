#!/usr/bin/env python3
"""Fixed-16 Y-fork ring prototype for reverse-a-list.

This is the direct experiment for the "16-n padding, then fork 16 slots"
design:

* read n; keep n in B; put 16-n in BP;
* fork 16-n padding clones (A=0);
* recover n from B and put n in BP;
* fork n real clones (A=value+2^21, B=2^21);
* all 16 clones share one countdown racetrack;
* padding exits halt; real exits debias and use the sole outgoing pipe.
* the master waits in a compact counted loop before opening the next round.

The two fork phases together always create exactly 16 clones.  A clone born
with BP=k makes exactly k laps, so within the real phase later input values
leave before earlier ones.
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "tools"))

import littleman as lm


C = 1 << 21

ROOM_RIGHT = 38
ROOM_BOTTOM = 30

MASTER_Y = 24
PAD_Y_X = 12
PAD_TEST_X = 15
REAL_Y_X = 31

WORKER_Y = 19
WORKER_TOP = 2
WORKER_LEFT = 3
WORKER_A_X = 20
WORKER_ENTRY_X = 15


def lit(n):
    return f"`{n}`"


def build():
    p = lm.Program()

    def put(x, y, ch):
        old = p.get(x, y)
        if old not in (" ", ch):
            raise AssertionError(f"collision at {(x, y)}: {old!r} vs {ch!r}")
        p.put(x, y, ch)

    def text(x, y, s):
        for i, ch in enumerate(s):
            put(x + i, y, ch)

    p.room(0, 0, ROOM_RIGHT + 1, ROOM_BOTTOM + 1)

    # One input pipe and one output pipe.
    p.input_room(-5, MASTER_Y - 1)
    p.pipe([(-2, MASTER_Y), (-1, MASTER_Y)])
    p.output_room(ROOM_RIGHT + 3, 20)
    p.pipe([(ROOM_RIGHT + 1, 21), (ROOM_RIGHT + 2, 21)])

    # ---- round setup -----------------------------------------------------
    #
    # A=n; B=n; A=16-n; BP=16-n.  B remains n across the padding loop.
    put(1, MASTER_Y, ">")
    text(2, MASTER_Y, "@rM" + lit(16) + "-b")
    put(PAD_TEST_X, MASTER_Y, "d")

    # ---- padding fork loop ----------------------------------------------
    #
    # d entered eastbound:
    #   BP>0 -> south, route around to PAD_Y;
    #   BP=0 -> east into the real-phase setup.
    put(PAD_TEST_X, MASTER_Y + 1, "v")
    put(PAD_TEST_X, MASTER_Y + 2, "<")
    put(8, MASTER_Y + 2, "^")
    put(8, 22, ">")
    put(PAD_Y_X, 22, "Y")

    # Padding clone: born north of Y, set A=0, then join worker entry.
    put(PAD_Y_X, 21, "0")
    put(PAD_Y_X, 20, ">")

    # Padding master: decrement BP, make a tiny loop, and re-enter d eastbound.
    put(PAD_Y_X, 23, "m")
    put(PAD_Y_X, MASTER_Y, ">")
    put(13, MASTER_Y, "v")
    put(13, MASTER_Y + 1, ">")
    put(14, MASTER_Y + 1, "^")
    put(14, MASTER_Y, ">")

    # ---- transition and real fork loop ----------------------------------
    #
    # At padding completion B still holds n:
    #   W -> A=n; b -> BP=n; literal/M -> B=C.
    put(16, MASTER_Y, "W")
    put(17, MASTER_Y, "b")
    text(18, MASTER_Y, lit(C))
    put(27, MASTER_Y, "M")

    # Repeated real stage: r, bias with +, fork.
    put(29, MASTER_Y, "r")
    put(30, MASTER_Y, "+")
    put(REAL_Y_X, MASTER_Y, "Y")

    # Real clone: born north, route west and merge with padding-clone path.
    put(REAL_Y_X, 22, "<")
    put(WORKER_ENTRY_X, 22, "^")
    put(WORKER_ENTRY_X, 20, "^")
    put(WORKER_ENTRY_X, WORKER_Y, ">")

    # Real master: decrement; while BP>0 return to r, otherwise go home.
    put(REAL_Y_X, MASTER_Y + 1, "m")
    put(REAL_Y_X, MASTER_Y + 2, "a")
    put(33, MASTER_Y + 2, "^")
    put(33, 23, "<")
    put(28, 23, "v")
    put(28, MASTER_Y, ">")

    # BP=0 goes south, loads a fixed cooldown count while travelling west,
    # then approaches the wait loop from below.  The cooldown prevents the
    # next round from starting while long-lived padding clones still circle.
    put(REAL_Y_X, 28, "<")
    for x, ch in zip(range(30, 24, -1), lit(100) + "b"):
        put(x, 28, ch)
    put(8, 28, "v")
    put(8, 29, ">")

    # Compact 12-tick master loop: 100 laps are comfortably longer than the
    # slowest 16-runner drain.  On BP=0, a falls through east to the return.
    put(12, 29, "a")
    put(12, 27, "<")
    put(10, 27, "m")
    put(8, 27, "v")

    # Cold return stays outside the live worker ring.  It crosses the ring's
    # vertical legs only after the cooldown guarantees every clone has halted.
    put(37, 29, "^")
    put(37, 18, "<")
    put(1, 18, "v")
    put(1, MASTER_Y, ">")

    # ---- shared 16-runner countdown ring -------------------------------
    #
    # Both clone paths meet below the ring, climb to (15,19), and enter a.
    # Positive BP turns north for a lap.  m is on the top leg, so BP=k
    # performs exactly k laps.  BP=0 exits east to X.
    put(WORKER_A_X, WORKER_Y, "a")
    put(WORKER_A_X, WORKER_TOP, "<")
    put(16, WORKER_TOP, "m")
    put(WORKER_LEFT, WORKER_TOP, "v")
    put(WORKER_LEFT, WORKER_Y, ">")

    # A=0 padding goes straight to H.  Biased real A>0 turns south, debiases,
    # sends through the room's only outgoing pipe, and halts.
    put(21, WORKER_Y, "X")
    put(22, WORKER_Y, "H")
    put(21, 20, "-")
    put(21, 21, ">")
    put(22, 21, "s")
    put(23, 21, "H")

    return p


if __name__ == "__main__":
    program = build()
    output = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "y-fixed16-ring-poc.man")
    program.save(output)
    print(program.render())
    print("footprint:", program.footprint())
    print("saved:", output)
