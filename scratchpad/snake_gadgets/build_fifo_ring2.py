#!/usr/bin/env python3
"""GADGET 2b -- the same body FIFO ring, but with INTERLEAVED push/pop.

This is the access pattern the real snake controller uses: every game tick
pushes the new head cell and (unless the snake grew) pops the tail cell.

Protocol: read an integer.
    v > 0  -> PUSH v   (no output)
    v = 0  -> POP      (emit the popped value)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import littleman as lm  # noqa: E402


def build():
    p = lm.Program()

    p.input_room(12, 1)
    p.put(13, 4, 'v'); p.put(13, 5, 'v')

    p.room(10, 6, 10, 7)                     # CTRL (10,6)-(19,12)
    # read + dispatch
    p.put(11, 7, '@'); p.put(12, 7, '>'); p.put(13, 7, 'r')
    p.put(14, 7, 'X'); p.put(15, 7, 'v')     # A>0 -> push arm, A==0 -> pop arm
    # push arm (A > 0): X turns CW east->south
    p.put(12, 8, '^'); p.put(13, 8, 's'); p.put(14, 8, '<')
    # pop arm (A == 0): straight east then down column 15
    p.put(15, 10, '>'); p.put(16, 10, 'r'); p.put(17, 10, 'v')
    p.put(17, 11, '<'); p.put(16, 11, 's'); p.put(15, 11, '<')
    p.put(12, 11, '^')                       # rejoin the read loop up column 12

    p.room(0, 6, 8, 7)                       # RELAY (0,6)-(7,12)
    p.put(1, 7, '@'); p.put(2, 7, '>'); p.put(3, 7, 'r'); p.put(4, 7, 'v')
    p.put(2, 8, '^'); p.put(3, 8, 's'); p.put(4, 8, '<')

    p.put(9, 8, '<'); p.put(8, 8, '<')       # FEED

    p.put(3, 13, 'v'); p.put(3, 14, '>')     # RETURN
    for x in range(4, 16):
        p.put(x, 14, '-')
    p.put(16, 14, '^'); p.put(16, 13, '^')

    p.put(20, 11, '>'); p.put(21, 11, '>')
    p.output_room(22, 10)
    return p


if __name__ == '__main__':
    prog = build()
    out = os.path.join(HERE, 'fifo_ring2.man')
    prog.save(out)
    print('wrote %s  %dx%d box=%d' % ((out,) + prog.footprint()))
    print(prog.render())
