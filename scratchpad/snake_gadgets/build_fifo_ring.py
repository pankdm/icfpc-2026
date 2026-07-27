#!/usr/bin/env python3
"""GADGET 2 -- the snake body FIFO ring (CTRL room + relay room + two pipes).

Rig:  I -> CTRL --FEED--> RELAY --RETURN--> CTRL -> O

CTRL reads integers from input.  A positive value is PUSHED into the ring; the
first 0 switches CTRL into the POP loop, which pops values off the ring and
emits them.  A correct FIFO therefore echoes the pushed values in the SAME
order.  When the ring runs dry the popping `r` parks forever (free) -- the
output has already settled, so the tick count is the interesting number.

Ring capacity = feed_len + 1 (the relay man's A register) + return_len.

    python3 build_fifo_ring.py [return_len_cells] > /dev/null   # writes .man
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import littleman as lm  # noqa: E402


def build(ret_span=13):
    """ret_span = number of horizontal cells in the RETURN pipe's long run."""
    p = lm.Program()

    # ---- I room ---------------------------------------------------------
    p.input_room(12, 1)                      # (12,1)-(14,3), I at (13,2)
    p.put(13, 4, 'v'); p.put(13, 5, 'v')     # INPUT pipe -> CTRL top wall (13,6)

    # ---- CTRL room ------------------------------------------------------
    p.room(10, 6, 10, 7)                     # (10,6)-(19,12), interior x 11..18, y 7..11
    # push loop: @ > r X v  /  ^ s <
    p.put(11, 7, '@'); p.put(12, 7, '>'); p.put(13, 7, 'r')
    p.put(14, 7, 'X'); p.put(15, 7, 'v')
    p.put(12, 8, '^'); p.put(13, 8, 's'); p.put(14, 8, '<')
    # fall-through column (A == 0) down to the pop loop
    p.put(15, 8, ' '); p.put(15, 9, ' ')
    # pop loop: > r v  /  ^ s <
    p.put(15, 10, '>'); p.put(16, 10, 'r'); p.put(17, 10, 'v')
    p.put(15, 11, '^'); p.put(16, 11, 's'); p.put(17, 11, '<')

    # ---- RELAY room -----------------------------------------------------
    p.room(0, 6, 8, 7)                       # (0,6)-(7,12), interior x 1..6, y 7..11
    p.put(1, 7, '@'); p.put(2, 7, '>'); p.put(3, 7, 'r'); p.put(4, 7, 'v')
    p.put(2, 8, '^'); p.put(3, 8, 's'); p.put(4, 8, '<')

    # ---- FEED pipe: CTRL left wall (10,8) -> RELAY right wall (7,8) ------
    p.put(9, 8, '<'); p.put(8, 8, '<')

    # ---- RETURN pipe: RELAY bottom (3,12) -> CTRL bottom (16,12) ---------
    x_end = 3 + ret_span                     # bend column of the long run
    p.put(3, 13, 'v')
    p.put(3, 14, '>')
    for x in range(4, x_end):
        p.put(x, 14, '-')
    p.put(x_end, 14, '^')
    p.put(x_end, 13, '^')
    assert x_end == 16, 'the return pipe must arrive under CTRL col 16'

    # ---- O room ---------------------------------------------------------
    p.put(20, 11, '>'); p.put(21, 11, '>')
    p.output_room(22, 10)                    # (22,10)-(24,12), O at (23,11)

    feed_len = 2
    return_len = 2 + (x_end - 4 + 1) + 1     # (3,13),(3,14) + run + (x_end,13)
    return p, feed_len, return_len


if __name__ == '__main__':
    prog, fl, rl = build()
    out = os.path.join(HERE, 'fifo_ring.man')
    prog.save(out)
    w, h, box = prog.footprint()
    print('wrote %s  %dx%d box=%d  feed=%d return=%d capacity=%d'
          % (out, w, h, box, fl, rl, fl + 1 + rl))
    print(prog.render())
