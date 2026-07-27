#!/usr/bin/env python3
"""Correctness rig for the FIVE-row main room (interior 8x5) in a roomy 16x16."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main5

W = H = 16
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


room(0, 2, 9, 8)                                    # main, interior x1..8 y3..7
for j, line in enumerate(main5.BASE):
    for i, ch in enumerate(line):
        if ch != ' ':
            put(1 + i, 3 + j, ch)

room(13, 0, 15, 2); put(14, 1, 'O')                 # output
room(0, 11, 2, 13); put(1, 12, 'I')                 # input
room(3, 11, 7, 14)                                  # relay, flow-in = south
put(4, 12, '>'); put(5, 12, '@'); put(6, 12, 'U')
put(6, 13, '<'); put(5, 13, 's'); put(4, 13, '^')

# main -> output (source above the north wall)
pipe([(5, 1), (5, 0), (6, 0), (7, 0), (8, 0), (9, 0), (10, 0), (11, 0), (12, 0)], (1, 0))
# main -> relay, exactly 2 cells (q timing depends on this being short)
pipe([(4, 9), (4, 10)], (0, 1))
# input -> main SOUTH wall (so U turns north)
pipe([(1, 10), (1, 9)], (0, -1))
# relay -> main SOUTH wall, 15 cells
pipe([(8, 12), (9, 12), (9, 13), (9, 14), (10, 14), (10, 13), (10, 12), (10, 11),
      (10, 10), (10, 9), (9, 9), (8, 9), (7, 9), (6, 9), (5, 9)], (0, -1))

out = "\n".join("".join(r).rstrip() for r in g) + "\n"
dest = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'rig16.man')
open(dest, 'w').write(out)
print("written", dest)
