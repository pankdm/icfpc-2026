#!/usr/bin/env python3
"""sort-numbers, 12x12 -> box 144.  Found by the exhaustive floorplan search in
scratchpad/sort12/ (drive5.py + search.py); the main room's control flow is
documented in scratchpad/sort12/main5.py.

Main room interior is 8 wide x 5 tall (70 cells) instead of the 8x7 the 13x13
champion used; that is what makes the four rooms plus a 16-cell return pipe fit
inside 144 cells.  Two geometry facts the search had to respect:
  * the main->relay pipe must stay short -- `q` reads the circulating count only
    ~11 ticks after the lap's last send, and the relay adds up to 6 more;
  * the relay->main return pipe alone must hold n-1 = 15 values, because lap 1
    reads from the input pipe and never drains the return pipe.
"""
import os
import sys

W = H = 12
ROOMS = [(0, 0, 9, 6), (7, 8, 11, 11), (0, 9, 2, 11), (3, 9, 5, 11)]
CELLS = [(2, 1, 'v'), (3, 1, 'M'), (4, 1, 'R'), (5, 1, 'm'), (6, 1, '<'), (7, 1, 'b'), (8, 1, '<'), (1, 2, '>'), (3, 2, 's'), (5, 2, 'q'), (6, 2, 'a'), (7, 2, '@'), (8, 2, 'U'), (10, 2, 'v'), (11, 2, '<'), (1, 3, '^'), (2, 3, 'v'), (3, 3, 'a'), (4, 3, 's'), (5, 3, 'W'), (6, 3, '+'), (7, 3, '<'), (10, 3, 'v'), (11, 3, '^'), (1, 4, 'W'), (2, 4, 'a'), (3, 4, '>'), (4, 4, 'm'), (5, 4, 'R'), (6, 4, '-'), (7, 4, 'X'), (8, 4, 'v'), (10, 4, 'v'), (11, 4, '^'), (1, 5, '^'), (2, 5, '<'), (3, 5, 'd'), (5, 5, 's'), (6, 5, '+'), (7, 5, '<'), (8, 5, '<'), (10, 5, 'v'), (11, 5, '^'), (10, 6, 'v'), (11, 6, '^'), (0, 7, '^'), (2, 7, 'v'), (5, 7, 'v'), (6, 7, '^'), (7, 7, '<'), (8, 7, '<'), (9, 7, '<'), (10, 7, '<'), (11, 7, '^'), (0, 8, '^'), (2, 8, '>'), (3, 8, '>'), (4, 8, 'v'), (5, 8, '>'), (6, 8, '>'), (8, 9, 'U'), (9, 9, 's'), (10, 9, 'v'), (1, 10, 'I'), (4, 10, 'O'), (8, 10, '^'), (9, 10, '@'), (10, 10, '<')]

g = [[" "] * W for _ in range(H)]


def put(x, y, ch):
    if g[y][x] != " ":
        raise SystemExit("collision at (%d,%d)" % (x, y))
    g[y][x] = ch


for x0, y0, x1, y1 in ROOMS:
    for x in range(x0, x1 + 1):
        put(x, y0, "-" if x0 < x < x1 else "+")
        put(x, y1, "-" if x0 < x < x1 else "+")
    for y in range(y0 + 1, y1):
        put(x0, y, "|")
        put(x1, y, "|")
for x, y, ch in CELLS:
    put(x, y, ch)

out = "\n".join("".join(r).rstrip() for r in g) + "\n"
dest = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "r12.man")
open(dest, "w").write(out)
