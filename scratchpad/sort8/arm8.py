#!/usr/bin/env python3
"""sort-numbers arm8: 8-tick greater arm + short lap-entry chain.

Compare cycle (run heads WEST, 'm' lives in the run so both arms drop it):
  run      U  m  -  X                      (4 cells)
  greater  X -CW-> +  s  d   -> U          (8 cycle)
  less     X -CCW-> + W  s ^ a -> U        (10 cycle)
  equal    X straight ^ > (join greater)   (10 cycle)

Loop cells for (ux,uy):
  row uy-1 : ux-4 '>'  ux-3 '>'  ux-2 '+'  ux-1 's'  ux 'd'   | merge ux+1
  row uy   : ux-4 '^'  ux-3 'X'  ux-2 '-'  ux-1 'm'  ux 'U'   | ux+1 'a'
  row uy+1 :           ux-3 '>'  ux-2 '+'  ux-1 'W'  ux 's'   | ux+1 '^'

Both lap exits land on the merge cell (ux+1,uy-1):
  greater: 'd' at (ux,uy-1) BP==0 -> straight east
  less   : 'a' at (ux+1,uy) BP==0 -> straight north

Lap entry re-uses the less-arm test: a man arriving at (ux+1,uy+1) goes north to
(ux+1,uy)'a'; BP>0 -> west into U, BP==0 -> north to the merge (that is the K==1
"output the last value" path, free).
"""
import os
import subprocess
import sys

REPO = "/Users/visenbaev/icfpc26"
GW = GH = 13

DIRCH = {(1, 0): '>', (-1, 0): '<', (0, 1): 'v', (0, -1): '^'}
DIRS = list(DIRCH)


def cw(d):
    return (-d[1], d[0])


def ccw(d):
    return (d[1], -d[0])


# ------------------------------------------------------------------ outer plan
def outer():
    """Everything except the main-room interior.  Returns dict (x,y)->char."""
    g = {}

    def put(x, y, ch):
        if (x, y) in g:
            raise ValueError("collision %r %r/%r" % ((x, y), g[(x, y)], ch))
        g[(x, y)] = ch

    def room(x0, y0, x1, y1):
        for x in range(x0, x1 + 1):
            put(x, y0, '+' if x in (x0, x1) else '-')
            put(x, y1, '+' if x in (x0, x1) else '-')
        for y in range(y0 + 1, y1):
            put(x0, y, '|')
            put(x1, y, '|')

    def pipe(path):
        for i in range(len(path) - 1):
            (x, y), (nx, ny) = path[i], path[i + 1]
            put(x, y, DIRCH[(nx - x, ny - y)])

    room(0, 0, 9, 8)                       # main
    room(10, 0, 12, 2); put(11, 1, 'I')    # input
    room(0, 10, 2, 12); put(1, 11, 'O')    # output
    room(5, 9, 9, 12)                      # relay
    for (x, y), ch in {(6, 10): 'U', (7, 10): 's', (8, 10): 'v',
                       (8, 11): '<', (7, 11): '@', (6, 11): '^'}.items():
        put(x, y, ch)

    pipe([(11, 3), (11, 4), (10, 4), (9, 4)])              # input -> main, dst row 4
    pipe([(4, 9), (4, 10), (5, 10)])                       # main -> relay   src x=4
    pipe([(3, 9), (3, 10), (2, 10)])                       # main -> output  src x=3
    pipe([(10, 11), (11, 11), (11, 12), (12, 12), (12, 11), (12, 10), (11, 10),
          (11, 9), (11, 8), (11, 7), (12, 7), (12, 6), (12, 5), (11, 5),
          (10, 5), (9, 5)])                                # relay -> main, dst row 5
    return g


OUTER = outer()
INTERIOR = [(x, y) for y in range(1, 8) for x in range(1, 9)]
Q_ROWS = {5, 6, 7}      # rows where 'q' picks the relay pipe (dst row 5) over input (row 4)
S_RELAY_X = range(4, 9)  # 's' columns that pick the relay pipe
S_OUT_X = range(1, 4)    # 's' columns that pick the output pipe


def loop_cells(ux, uy):
    return {
        (ux - 4, uy - 1): '>', (ux - 3, uy - 1): '>', (ux - 2, uy - 1): '+',
        (ux - 1, uy - 1): 's', (ux, uy - 1): 'd',
        (ux - 4, uy): '^', (ux - 3, uy): 'X', (ux - 2, uy): '-',
        (ux - 1, uy): 'm', (ux, uy): 'U', (ux + 1, uy): 'a',
        (ux - 3, uy + 1): '>', (ux - 2, uy + 1): '+', (ux - 1, uy + 1): 'W',
        (ux, uy + 1): 's', (ux + 1, uy + 1): '^',
    }


def render(cells):
    g = [[' '] * GW for _ in range(GH)]
    for (x, y), ch in cells.items():
        g[y][x] = ch
    return "\n".join("".join(r).rstrip() for r in g) + "\n"


def grade(path):
    out = subprocess.run([sys.executable, REPO + "/tools/grade_fast.py",
                          "sort-numbers", path], capture_output=True, text=True).stdout
    return out
