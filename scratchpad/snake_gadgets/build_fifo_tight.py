#!/usr/bin/env python3
"""Gadget 2b: the FIFO ring at its floor -- a 10-cell push+pop loop.

Ring: A --pipe1--> relay --pipe2--> A (a self-loop pipe is illegal, hence the
relay's two-op r,s man).  Room A runs a fixed push-then-pop cycle with no
branch, so the whole loop is 10 cells:

    >  @  r(input)  s(push)  v          top wall  = pipe1 out
    ^     s(emit)   r(pop)   <          bottom wall = pipe2 in + output out

Ticks/pair measured here are the FLOOR for a body FIFO; anything above it in a
real build is walking, not pipe cost.  Ring capacity is set by `ring_extra`.

usage: build_fifo_tight.py [ring_extra] [out.man]
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
from littleman import Program

EXTRA = int(sys.argv[1]) if len(sys.argv) > 1 else 0
OUT = sys.argv[2] if len(sys.argv) > 2 else 'fifo_tight.man'
RX = 8 + EXTRA                        # relay x -> ring capacity

p = Program()
p.room(0, 0, 7, 4)                    # A: x 0..6 y 0..3, interior 1..5 / 1..2
p.text(1, 1, '>@rsv')
p.text(1, 2, '^ s r<'[:5])            # (1,2)^ (2,2)s (3,2)space (4,2)r (5,2)<
p.text(4, 2, 'r<')

p.input_room(-5, 0)                   # I at (-4,1) -> A left wall (0,1)
p.pipe([(-2, 1), (-1, 1)])
p.output_room(-5, 5)                  # O at (-4,6)
p.pipe([(2, 4), (2, 6), (-2, 6)], end_direction='W')   # A bottom wall (2,3) -> O

p.room(RX, 0, 6, 4)                   # relay: interior RX+1..RX+4 / 1..2
p.text(RX + 1, 1, '>rsv')
p.text(RX + 1, 2, '^')
p.text(RX + 3, 2, '@<')

p1 = [(4, -1), (4, -3), (RX + 2, -3), (RX + 2, -1)]    # A top -> relay top
p2 = [(RX + 2, 4), (RX + 2, 6), (5, 6), (5, 4)]        # relay bottom -> A bottom
p.pipe(p1, end_direction='S')
p.pipe(p2, end_direction='N')

def plen(pts):
    n = 1
    for i in range(len(pts) - 1):
        n += abs(pts[i + 1][0] - pts[i][0]) + abs(pts[i + 1][1] - pts[i][1])
    return n

p.save(os.path.join(HERE, OUT))
print(p.render())
print('footprint', p.footprint(), 'ring capacity', plen(p1) + plen(p2))
