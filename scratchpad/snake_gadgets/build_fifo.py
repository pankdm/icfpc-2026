#!/usr/bin/env python3
"""Gadget 2: the snake body as a PIPE FIFO ring.

Room A is the single access point: it pushes the new head into the ring and
pops the tail out of it.  A self-loop pipe is illegal, so the ring is
A --pipe1--> RELAY --pipe2--> A, with a two-instruction relay man (r,s) that
strictly alternates.  Ring capacity = len(pipe1) + len(pipe2) (+1 in the relay).

Command protocol on the input pipe (A's `X` branches on sign(A)):
    v > 0   push v        (A>0 -> cw -> south -> `s` nearest pipe1 on the bottom wall)
    v < 0   pop, emit it  (A<0 -> ccw -> north -> `r` nearest pipe2 on the top wall)

usage: build_fifo.py [relay_x] [out.man]
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
from littleman import Program

RX = int(sys.argv[1]) if len(sys.argv) > 1 else 60
OUT = sys.argv[2] if len(sys.argv) > 2 else 'fifo.man'

p = Program()

# ---- room A: push/pop access point ---------------------------------------
p.room(0, 0, 14, 12)                 # x 0..13, y 0..11 ; interior 1..12 / 1..10
p.text(1, 5, '>rX')                  # (1)=re-entry  (2)=r cmd  (3)=X sign branch
p.text(3, 6, 's')                    # push arm: nearest pipe = pipe1 (bottom wall)
p.text(3, 7, '<')
p.man(2, 7)
p.text(1, 7, '^')
p.text(3, 3, 'r')                    # pop arm: nearest pipe = pipe2 (top wall)
p.text(3, 2, '>')
p.text(11, 2, 'sv')                  # send popped value to O, then turn back
p.text(12, 7, '<')

p.input_room(-5, 4)                  # I at (-4,5) -> A's left wall (0,5)
p.pipe([(-2, 5), (-1, 5)])
p.output_room(16, 1)                 # A's right wall (13,2) -> O at (17,2)
p.pipe([(14, 2), (15, 2)])

# ---- relay room -----------------------------------------------------------
p.room(RX, 4, 6, 4)                  # x RX..RX+5, y 4..7 ; interior RX+1..RX+4 / 5..6
p.text(RX + 1, 5, '>rsv')
p.text(RX + 1, 6, '^')
p.text(RX + 3, 6, '@<')

# ---- the ring: A -> relay -> A -------------------------------------------
p1 = [(3, 12), (3, 14), (RX + 2, 14), (RX + 2, 8)]
p2 = [(RX + 2, 3), (RX + 2, -3), (3, -3), (3, -1)]
p.pipe(p1)
p.pipe(p2)

def plen(pts):
    n = 1
    for i in range(len(pts) - 1):
        n += abs(pts[i + 1][0] - pts[i][0]) + abs(pts[i + 1][1] - pts[i][1])
    return n

cap = plen(p1) + plen(p2)
path = os.path.join(HERE, OUT)
p.save(path)
print(p.render())
print('footprint', p.footprint(), 'pipe1', plen(p1), 'pipe2', plen(p2), 'ring capacity', cap)
