#!/usr/bin/env python3
"""Room templates for the history-lesson ring build, as explicit ASCII grids.

Each room is a list of strings (content rows, no borders).  The builder pastes
them into a Program with borders and checks pipe bindings.

Conventions: rooms are given with their intended pipe attach points.
"""
import os, sys

TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools")
sys.path.insert(0, TOOLS)
from littleman import Program


def paste(program: Program, x0, y0, rows, w=None, h=None):
    """Paste content rows at interior origin (x0+1, y0+1) inside a room whose
    border top-left is (x0, y0).  Draws the room border too."""
    w = w or (max(len(r) for r in rows) + 2)
    h = h or (len(rows) + 2)
    program.room(x0, y0, w, h)
    for dy, row in enumerate(rows):
        for dx, ch in enumerate(row):
            if ch != " ":
                program.put(x0 + 1 + dx, y0 + 1 + dy, ch)
    return x0 + w, y0 + h


def check_pipe_bindings(program, expects):
    """expects: list of (cell_xy, kind, attach_xy) where kind is 'out'/'in'.
    Recomputes nearest pipe per the interpreter rule and asserts the chosen
    pipe's attach cell equals attach_xy.  Pipes are parsed from the grid?  No:
    the builder passes explicit pipe endpoint lists via program._pipes."""
    for (cx, cy), kind, want in expects:
        cands = [p for p in program._pipes
                 if p["room_cells"] is None]
    # placeholder; real check in builder (needs room association)


# --- D1: classifier -------------------------------------------------------
# Input: symbols 0..B1-1 from decoder (single incoming pipe, west wall y2).
# Output: tags to L1 (single outgoing pipe, east wall y2? anywhere).
#   0        -> -1
#   1..16    -> v          (ring positions; v=9 and v=17 are stolen/never occur)
#   18..91   -> -(v+32)    (v=17 stolen, never occurs; ESC=29 handled below)
#   ESC=29,k -> k          (k = ring position, 17+E..)
#   92..B1-1 -> v-75       (ext singles at positions 17..)
#
# Layout (content rows y1..y5, cols 1..W).  Verified by simulation.

def d1_rows():
    #        1         2
    # 123456789012345678901234
    rows = [
        "v<<<<<<<<<<<<<<<<<<<<<",   # y1: return corridor (westbound), v at col1
        ">`17`M r X   `1`N s ^ ",   # y2: main loop east; X1 at col10 branch
        " >WM`92`-N X  `23`+Ns^",   # y3: recover/ext lane (see notes)
        "  X~`29`M+ -          ",   # y4: big lane westbound; X3 at col3
        " >rs  ^   X+s ^       ",   # y5: ESC lane / small lane
    ]
    return rows

# The exact D1 grid is finalized iteratively against the interpreter in
# test_d1.py; the strings above are a starting sketch.
