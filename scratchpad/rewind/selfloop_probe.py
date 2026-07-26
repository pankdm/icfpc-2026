#!/usr/bin/env python3
"""Probe: can a pipe have its source AND destination on the same room?
If yes, the belt needs no HOP relay room at all."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools'))
from littleman import Program

p = Program()
P = p.put

# A room: cols 6-21, rows 0-6 ; interior cols 7-20 rows 1-5
p.room(6, 0, 16, 7)
p.output_room(0, 0)

# init: A=7, then walk to the loop send
for i, c in enumerate("@`7`"):
    P(7 + i, 1, c)
P(20, 1, 'v')
P(20, 5, '<')
P(19, 5, 's')          # nearest outgoing = loop source (22,5)
P(18, 5, 'r')          # nearest incoming = loop dest (9,7)
P(8, 5, '^')
P(8, 3, '<')
P(7, 3, 's')           # nearest outgoing = out pipe source (5,1)

p.pipe([(5, 1), (3, 1)])                                   # A -> O
p.pipe([(22, 5), (24, 5), (24, 8), (9, 8), (9, 7)])        # A -> A  self loop

out = os.path.join(os.path.dirname(__file__), 'selfloop_probe.man')
p.save(out)
print(out, p.footprint())
