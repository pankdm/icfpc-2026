#!/usr/bin/env python3
"""Standalone rig for the FLAG-EMITTING mask strip (mask-zero-2col + '1 s' on the
return leg, so every mask yields a flag: 1 = ok/zero, 0 = duplicate)."""
import sys, os
sys.path.insert(0, "/Users/visenbaev/icfpc26/tools")
from littleman import Program

STRIP = [
    "v<",   # 0  <- return top: '<' turns west, 'v' drops back in
    "vs",   # 1  <- entry row (init tail lands on 'v'); 's' sends the flag
    "r1",   # 2  <- receive mask ; '1' loads the ok-flag
    "bM",   # 3
    "~~",   # 4
    "-N",   # 5
    "aX",   # 6
    "~0",   # 7
    ">X",   # 8
    " s",   # 9  <- duplicate exit: sends A=0
    " H",   # 10
]

def strip(p, x, y):
    """Place a 2-col strip whose top-left is (x,y). Entry: a man arriving at (x,y)
    heading south with B=-1."""
    for j, row in enumerate(STRIP):
        for i, ch in enumerate(row):
            if ch != " ":
                p.put(x + i, y + j, ch)

def build():
    p = Program()
    p.input_room(0, 0)
    p.room(6, 0, 8, 13)          # gadget room: interior x7..12, y1..11
    p.text(7, 2, "@1NM")         # shared init: A=1, A=-1, B=-1
    strip(p, 11, 1)
    p.output_room(16, 10)
    p.pipe([(3, 1), (5, 1)])
    p.pipe([(14, 11), (15, 11)])
    return p

if __name__ == "__main__":
    p = build()
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "strip1.man")
    p.save(out)
    print(out, p.footprint())
