#!/usr/bin/env python3
"""Brackets box budget: room rectangles vs the 16x16 target, and per-room
op/turn/blank split so the achievable interior density is a measured number
rather than a guess."""
import sys, collections
sys.path.insert(0, "/Users/visenbaev/icfpc26/solutions/brackets")
import p5_build as B

TURN = set("<>^v")
ROOMS = [
    ("M", B.M9_W, B.M9_H, B.M9_CELLS),
    ("P", B.P_W, B.P_H, B.P_CELLS),
    ("C", B.C_W, B.C_H, B.C_CELLS),
]
tot = 0
print("room  rect   area  interior  cells  turns  realops  blanks  fill")
for name, w, h, cells in ROOMS:
    area = w * h
    tot += area
    inter = (w - 2) * (h - 2)
    turns = sum(1 for (_, _, c) in cells if c in TURN)
    real = len(cells) - turns
    print("%-4s %2dx%-2d %4d   %2dx%-2d   %4d  %5d  %6d  %6d  %3d%%" % (
        name, w, h, area, w - 2, h - 2, len(cells), turns, real,
        inter - len(cells), 100 * len(cells) // inter))
tot += 9 + 9
print("rooms total %d   I/O 3x3 each" % tot)
for box in (17, 16, 15):
    print("box %dx%d = %4d  rooms %d + 4 pipes x2 = %d  ->  %s (slack %d)" % (
        box, box, box * box, tot, tot + 8,
        "FITS" if tot + 8 <= box * box else "IMPOSSIBLE", box * box - tot - 8))

# What rectangle would each room need for the box to reach 16x16?
print()
print("width  = M_w + P_w  (P east-adjacent to M)")
print("height = M_h + C_h  (C south-adjacent to M)")
print("so 16x16 needs M <= 10x10, i.e. interior 8x8 = 64 cells for M's %d"
      % len(B.M9_CELLS))
print("current M interior 9x9 = 81 -> required fill %d%% (now %d%%)"
      % (100 * len(B.M9_CELLS) // 64, 100 * len(B.M9_CELLS) // 81))
