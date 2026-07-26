#!/usr/bin/env python3
"""Gadget 1: 16x16 occupancy as FOUR 64-bit registers (4 parked men holding B).

Protocol.  One command pipe per quarter.  A transaction is TWO values
(or_mask, and_mask); the quarter man runs a fixed 8-op loop

    r | W ~ s      A=or ; A=B|or ; A<->B (A=old,B=new) ; A=old^new ; send
    r & M          A=and ; A=B&and ; B=new

so every transaction returns "the bits this OR newly set" -- which IS the
occupancy test -- and can set and/or clear in the same pass:

    SET(i)  -> (mask, -1)     returns mask if the cell was FREE, 0 if OCCUPIED
    CLR(i)  -> (0, ~mask)     returns 0

The controller reads (op, i) from input, computes q=i>>6 and mask=1<<(i&63)
with a single `/` by 64 (quotient AND remainder in one op), puts q in BP and
decodes it with x ] x into four arms, each arm's `s` being nearest its own
quarter's pipe.  Results are merged by a collector man (R,s) into O.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
from littleman import Program

RY = 12                      # controller "start" row
ARM = {0: RY - 9, 2: RY - 3, 1: RY + 3, 3: RY + 9}   # quarter -> arm row
RET = RY + 11                # controller return row
T = 29                       # tree entry column

p = Program()

# ---- input room -----------------------------------------------------------
p.input_room(0, RY - 1)
p.pipe([(3, RY), (5, RY)])

# ---- controller room ------------------------------------------------------
p.room(6, RY - 10, 31, 23)           # x 6..36, y 2..24 ; interior 7..35 / 3..23
p.text(7, RY, '>rbx')                # (7)= re-entry, r=op, b=BP, x=2-way on op
p.man(8, RET)                        # starts on the return row, walks east

# SET prep (op odd -> cw -> south), row RY+1
p.text(10, RY + 1, '>`64`Mr/b1{M1NW')   # A=mask (or), B=-1 (and)
p.text(28, RY + 1, '^')
# CLR prep (op even -> ccw -> north), row RY-1
p.text(10, RY - 1, '>`64`Mr/b1{M1N~M0')  # A=0 (or), B=~mask (and)
p.text(28, RY - 1, 'v')
p.text(28, RY, '>')                  # merge

# 4-way quarter decode: x  (bit0)  ->  '>' ] x  (bit1)
p.text(T, RY, 'x')
p.text(T, RY - 6, '>]x')
p.text(T, RY + 6, '>]x')
for q, row in ARM.items():
    p.text(T + 2, row, '>sWsv')      # send or, swap, send and, return
p.text(T + 6, RET, '<')
p.text(7, RET, '^')

# ---- four quarter rooms ---------------------------------------------------
for q, row in ARM.items():
    top = row - 1
    p.room(42, top, 10, 4)           # x 42..51, interior 43..50 / top+1..top+2
    p.text(43, top + 1, '>@r|W~sv')
    p.text(43, top + 2, '^')
    p.text(47, top + 2, 'M&r<')
    p.pipe([(37, row), (41, row)])   # controller -> quarter
    p.pipe([(52, row), (55, row)])   # quarter -> collector

# ---- collector + output ---------------------------------------------------
p.room(56, RY - 10, 6, 23)           # x 56..61, interior 57..60 / 3..23
p.text(57, RY - 8, '>Rsv')
p.text(57, RY - 7, '^')
p.text(59, RY - 7, '@<')
p.pipe([(62, RY - 8), (63, RY - 8)])
p.output_room(64, RY - 9)

path = os.path.join(HERE, 'occ4.man')
p.save(path)
print(p.render())
print('footprint', p.footprint())
