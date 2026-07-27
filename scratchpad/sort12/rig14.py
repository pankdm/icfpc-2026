#!/usr/bin/env python3
"""Correctness rig: the new sort-numbers main room (interior 8x6) in a roomy 14x14
box.  Only the logic is under test here; the 12x12 packing is a separate problem.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mainroom

W = H = 14
g = [[' '] * W for _ in range(H)]


def put(x, y, ch):
    if not (0 <= x < W and 0 <= y < H):
        raise SystemExit("oob (%d,%d)" % (x, y))
    if g[y][x] != ' ':
        raise SystemExit("collision (%d,%d): %r vs %r" % (x, y, g[y][x], ch))
    g[y][x] = ch


def room(x0, y0, x1, y1):
    for x in range(x0, x1 + 1):
        put(x, y0, '-' if x0 < x < x1 else '+')
        put(x, y1, '-' if x0 < x < x1 else '+')
    for y in range(y0 + 1, y1):
        put(x0, y, '|'); put(x1, y, '|')


D = {(1, 0): '>', (-1, 0): '<', (0, 1): 'v', (0, -1): '^'}


def pipe(cells, last_dir):
    for i in range(len(cells) - 1):
        (x, y), (nx, ny) = cells[i], cells[i + 1]
        put(x, y, D[(nx - x, ny - y)])
    put(cells[-1][0], cells[-1][1], D[last_dir])


room(0, 0, 9, 7)
for j, line in enumerate(mainroom.BASE):
    for i, ch in enumerate(line):
        if ch != ' ':
            put(1 + i, 1 + j, ch)

room(11, 0, 13, 2); put(12, 1, 'I')                 # input
room(8, 10, 10, 12); put(9, 11, 'O')                # output
room(0, 10, 4, 13)                                  # relay, flow-in = south
for (x, y), ch in mainroom.relay_cells(3, 2, (0, 1))[0].items():
    put(1 + x, 11 + y, ch)

pipe([(12, 3), (12, 4), (11, 4), (10, 4)], (-1, 0))     # input -> main east wall
pipe([(2, 8), (2, 9)], (0, 1))                          # main -> relay top wall
pipe([(9, 8), (9, 9)], (0, 1))                          # main -> output top wall
pipe([(5, 13), (6, 13), (7, 13), (8, 13), (9, 13), (10, 13), (11, 13),
      (12, 13), (13, 13), (13, 12), (13, 11), (13, 10), (13, 9), (13, 8),
      (13, 7), (13, 6), (12, 6), (11, 6), (10, 6)], (-1, 0))   # relay -> main

out = "\n".join("".join(r).rstrip() for r in g) + "\n"
dest = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'rig14.man')
open(dest, 'w').write(out)
print("written", dest)
