#!/usr/bin/env python3
"""Gadget 1a: index -> (quarter, bitmask) decode.

Reads i (0..255), emits q = i>>6 then mask = 1 << (i&63).
Uses `/` with B=64 to get BOTH quotient and remainder in one op.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
from littleman import Program

p = Program()
p.input_room(0, 1)                     # I at (1,2)
p.pipe([(3, 2), (5, 2)])               # -> controller left wall (6,2)
p.room(6, 0, 16, 5)                    # x 6..21, interior 7..20 / y 1..3
p.man(8, 2)
p.text(7, 2, '>')                      # loop re-entry: face east
code = '`64`Mr/s1{sv'
p.text(9, 2, code)                     # x 9..20
p.text(20, 3, '<')                     # turn west on the return row
p.text(7, 3, '^')                      # turn north back into (7,2)
p.pipe([(22, 2), (23, 2)])             # controller right wall -> O
p.output_room(24, 1)

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mask.man')
p.save(path)
print(p.render())
print(p.footprint())
