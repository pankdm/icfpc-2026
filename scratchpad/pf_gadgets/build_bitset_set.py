#!/usr/bin/env python3
"""PF GADGET 1b -- the 256-bit set, SET-ONLY.  This is pathfinder's hot path.

Why SET-only.  Pathfinder never needs CLR *during* the BFS: keep ONE word set
`blocked = walls | visited`.  Then

    SET(n) returns non-zero  <=>  n was neither a wall nor already visited

so the whole BFS neighbour test (wall check + visited check + mark visited) is
a SINGLE transaction of ONE value in and ONE value out.  snake's occ4 carried a
second `r & M` pair only to support CLR, and a leading `r b x` to choose between
SET and CLR prep rows; deleting all of that is worth ~2x per transaction.
(The per-round reset `blocked := walls` is a separate, rare path: each quarter
man reloads B from a one-value holding ring.)

Geometry is occ4's, which is oracle-proven: 4-way decode `x` at (T,RY), `>]x`
at (T,RY+-6), arms at RY-9/-3/+3/+9.  Only the CLR machinery is gone.

  controller row:  > `64` M r / b 1 {        x
                     A=64  B=64 A=i  A=q,B=i&63  BP=q  A=1  A=1<<(i&63)

Transaction:  in  i (0..255)   ->   out  (old ^ new)

usage: build_bitset_set.py [out.man]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
from littleman import Program                                  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'bitset_set.man')

RY = 12                                   # controller centre / code row
ARM = {0: RY - 9, 2: RY - 3, 1: RY + 3, 3: RY + 9}
RET = RY + 11                             # return row
T = 22                                    # decode-tree entry column

p = Program()

p.input_room(0, RY - 1)
p.pipe([(3, RY), (5, RY)])

# ---------------------------------------------------------------- controller
p.room(6, RY - 10, 24, 23)                # x 6..29, interior 7..28 / RY-9..RY+11
p.text(7, RY, '>`64`Mr/b1{')              # re-entry + index -> (BP=q, A=mask)
p.man(8, RET)                             # spawn on the return row, facing east

p.text(T, RY, 'x')                        # bit0 of q
p.text(T, RY - 6, '>]x')                  # bit1, north half
p.text(T, RY + 6, '>]x')                  # bit1, south half
for q, row in ARM.items():
    p.text(T + 2, row, '>sv')             # send mask to quarter q, then head down
p.text(T + 4, RET, '<')                   # the 'v' column, not the '>' column
p.text(7, RET, '^')

# ------------------------------------------------------------ quarter rooms
for q, row in ARM.items():
    top = row - 1
    p.room(34, top, 10, 4)                # interior 35..42 / top+1..top+2
    p.text(35, top + 1, '>@r|W~sv')       # A=mask; A=B|mask=new; A=old,B=new;
    p.text(35, top + 2, '^')              #   A=old^new; send
    p.text(42, top + 2, '<')
    p.pipe([(30, row), (33, row)])        # controller -> quarter
    p.pipe([(44, row), (47, row)])        # quarter -> collector

# ------------------------------------------------------- collector + output
p.room(48, RY - 10, 6, 23)                # interior 49..52
p.text(49, RY, '>Rsv')
p.text(49, RY + 1, '^')
p.text(51, RY + 1, '@<')
p.pipe([(54, RY), (55, RY)])
p.output_room(56, RY - 1)

p.save(OUT)
print(p.render())
print('wrote %s  %dx%d box=%d' % ((OUT,) + p.footprint()))
