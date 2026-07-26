"""Standalone q-based selection sort without an in-stream sentinel.

At each pass boundary the short feed pipe has drained through the relay, so every
remaining value is in the (18-cell) return pipe.  ``q`` snapshots that pipe's
depth into BP.  The controller keeps the first value as the current minimum,
then consumes exactly BP-1 more values, returning every non-minimum value to the
ring.  The minimum is emitted and a deliberately long return path gives the
relay time to drain the feed pipe before the next ``q``.

No integer is reserved as a marker; values stay unencoded throughout.
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

    # Controller: interior x=1..25, y=6..50.
    p.room(0, 5, 27, 47)

    # Input enters through the top wall.
    p.input_room(12, 0)
    p.pipe([(13, 3), (13, 4)])

    # Output leaves through the bottom wall.
    p.output_room(23, 54)
    p.pipe([(24, 52), (24, 53)])

    # Relay room.  FEED is the short left-hand pipe; RET is the 18-cell pipe
    # leaving the relay's top and entering the controller at (27,20).
    p.room(30, 32, 6, 7)
    p.pipe([(27, 34), (29, 34)])
    p.pipe([(33, 31), (33, 20), (27, 20)])
    p.man(31, 34)
    put(32, 34, ">")
    put(33, 34, "r")
    put(34, 34, "v")
    put(32, 35, "^")
    put(33, 35, "s")
    put(34, 35, "<")

    # LOAD: read n, then copy exactly n raw values to FEED.
    p.man(12, 6)
    put(13, 6, "r")
    put(14, 6, "b")
    put(15, 6, "v")
    put(15, 7, ">")
    put(16, 7, "r")
    put(17, 7, "s")
    put(18, 7, "m")
    put(19, 7, "d")  # BP>0: south to loop; BP==0: east to the pass delay.
    put(19, 8, "<")
    put(15, 8, "^")

    # Initial/pass delay.  The last LOAD send has ample time to cross FEED and
    # be sent by the relay before q executes.
    put(20, 7, "v")
    put(20, 25, ">")

    # PASS: q sees RET (not INPUT), because RET's controller attachment is much
    # nearer.  Empty RET means the round is complete.
    put(21, 25, "q")
    put(22, 25, "d")  # BP>0: south; BP==0: east to LOAD.
    put(22, 26, "r")
    put(22, 27, "M")  # B = current minimum.
    put(22, 28, "m")  # The first of q values has been consumed.

    # Shared scan check, always entered heading south.
    put(22, 32, "v")
    put(22, 35, "d")  # BP>0: west to scan; BP==0: south to emit.
    put(21, 35, "m")
    put(20, 35, "r")
    put(19, 35, "-")
    put(18, 35, "X")  # token-min: positive=N, zero=W, negative=S.

    # token > min: restore and return token to FEED.
    put(18, 34, "+")
    put(18, 33, "s")
    put(18, 32, ">")

    # token == min: either copy can remain the minimum.
    put(17, 35, "+")
    put(16, 35, "s")
    put(15, 35, "^")
    put(15, 32, ">")

    # token < min: return the old minimum and keep token in B.
    put(18, 36, "+")
    put(18, 37, "W")
    put(18, 38, "s")
    put(18, 39, ">")
    put(24, 39, "^")
    put(24, 32, "<")

    # EMIT: BP reached zero, so B is the pass minimum.  This send is nearest the
    # output pipe; the three scan sends above are nearest FEED.
    put(22, 48, "W")
    put(22, 49, ">")
    put(24, 49, "s")
    put(25, 49, "v")
    put(25, 50, "<")

    # Long return path doubles as the inter-pass drain delay.
    put(5, 50, "^")
    put(5, 25, ">")

    # q==0: route back to LOAD for the next input round.
    put(24, 25, "^")
    put(24, 9, "<")
    put(10, 9, "^")
    put(10, 6, ">")

    return p, placed


if __name__ == "__main__":
    program, _ = build()
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "q-ring.man")
    program.save(out)
    print(program.render())
    print("footprint", program.footprint())
