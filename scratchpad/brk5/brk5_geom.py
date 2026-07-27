#!/usr/bin/env python3
"""Column budget for a 3-row C in a 16-wide brackets box.

The 256 enumeration prices rooms by AREA. It does not price the INPUT ROOM,
which p6_build places to C's LEFT together with two pipe columns:

    cx = M_w - 6;  input_room(cx - 5, 13);  pipes at cx-1, cx-2

so columns 0..cx-1 are consumed before C starts, and cx-5 >= 0 forces cx >= 5.
C therefore begins at column >= 5 and, in a 16-wide box, can be at most 11
wide -> interior 9 x 3 = 27 slots.
"""
import sys
sys.path.insert(0, '/Users/visenbaev/icfpc26/solutions/brackets')
import p6_build as B

n = len(B.C_CELLS)
for Mw in (10, 11):
    cx = Mw - 6
    cmax = 16 - cx
    print(f'M_w={Mw}: cx={cx} (input room at {cx-5}), C starts col {cx}, '
          f'max C width {cmax} -> interior {cmax-2}x3 = {(cmax-2)*3} slots '
          f'for {n} cells -> {"FITS" if (cmax-2)*3 >= n else "SHORT by %d" % (n-(cmax-2)*3)}')
print(f'\nbrk3 target C 15x5 needs 15 columns starting at col {11-6}: '
      f'ends at col {11-6+15-1} > 15 -> does not fit a 16-wide box '
      f'unless the input room relocates.')
