"""Compact layout of the q-delimited, sentinel-free selection sort.

This preserves build_q.py's controller and relay logic while:

* deleting timing slack down to the shortest public-case-safe corridors;
* tucking the input and output rooms into the controller's right margin; and
* shortening the feed pipe and folding the return pipe upward.
"""

import os
import sys

sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "tools",
    ),
)
import littleman as lm


def build():
    p = lm.Program()
    placed = {}

    def put(x, y, ch):
        if (x, y) in placed and placed[(x, y)] != ch:
            raise SystemExit(f"COLLISION {(x, y)}: {placed[(x, y)]} vs {ch}")
        placed[(x, y)] = ch
        p.put(x, y, ch)

    # Controller: interior x=1..15, y=1..24.
    p.room(0, 0, 17, 26)

    # I/O rooms occupy otherwise-unused space beside the controller.
    p.input_room(19, 0)
    p.pipe([(18, 1), (17, 1)])
    p.output_room(19, 22)
    p.pipe([(17, 23), (18, 23)])

    # Relay and the capacity-preserving folded return pipe.
    p.room(19, 13, 6, 7)
    p.pipe([(17, 15), (18, 15)])
    p.pipe([(22, 12), (22, 4), (17, 4)])
    p.man(20, 15)
    put(21, 15, ">")
    put(22, 15, "r")
    put(23, 15, "v")
    put(21, 16, "^")
    put(22, 16, "s")
    put(23, 16, "<")

    # LOAD: read n, then copy exactly n raw values to FEED.
    p.man(3, 1)
    put(4, 1, "r")
    put(5, 1, "b")
    put(6, 1, "v")
    put(6, 2, ">")
    put(7, 2, "r")
    put(8, 2, "s")
    put(9, 2, "m")
    put(10, 2, "d")
    put(10, 3, "<")
    put(6, 3, "^")

    # Initial/pass delay.
    put(11, 2, "v")
    put(11, 8, ">")

    # PASS: q snapshots the return pipe.
    put(12, 8, "q")
    put(13, 8, "d")
    put(13, 9, "r")
    put(13, 10, "M")
    put(13, 11, "m")

    # Shared scan check.
    put(13, 13, "v")
    put(13, 16, "d")
    put(12, 16, "m")
    put(11, 16, "r")
    put(10, 16, "-")
    put(9, 16, "X")

    # token > min
    put(9, 15, "+")
    put(9, 14, "s")
    put(9, 13, ">")

    # token == min
    put(8, 16, "+")
    put(7, 16, "s")
    put(6, 16, "^")
    put(6, 13, ">")

    # token < min
    put(9, 17, "+")
    put(9, 18, "W")
    put(9, 19, "s")
    put(9, 20, ">")
    put(14, 20, "^")
    put(14, 13, "<")

    # EMIT and inter-pass return path.
    put(13, 22, "W")
    put(13, 23, ">")
    put(14, 23, "s")
    put(15, 23, "v")
    put(15, 24, "<")
    put(1, 24, "^")
    put(1, 8, ">")

    # q==0: return to LOAD for the next round.
    put(14, 8, "^")
    put(14, 4, "<")
    put(2, 4, "^")
    put(2, 1, ">")

    return p, placed


if __name__ == "__main__":
    program, _ = build()
    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "q-ring-compact.man"
    )
    program.save(out)
    print(program.render())
    print("footprint", program.footprint())
