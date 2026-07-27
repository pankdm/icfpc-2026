#!/usr/bin/env python3
"""Probe: is a pipe from a room back to the SAME room legal?
If yes, the sort-numbers relay room (20 cells) can be deleted entirely.
Writes scratchpad/sort12/selfpipe.man
"""
import os, sys

W, H = 14, 10
g = [[' '] * W for _ in range(H)]

def put(x, y, ch):
    if g[y][x] != ' ':
        raise SystemExit("collision at (%d,%d): %r vs %r" % (x, y, g[y][x], ch))
    g[y][x] = ch

def room(x0, y0, x1, y1):
    for x in range(x0, x1 + 1):
        put(x, y0, '-' if x0 < x < x1 else '+')
        put(x, y1, '-' if x0 < x < x1 else '+')
    for y in range(y0 + 1, y1):
        put(x0, y, '|'); put(x1, y, '|')

def pipe(path):
    d = {(1, 0): '>', (-1, 0): '<', (0, 1): 'v', (0, -1): '^'}
    for i in range(len(path) - 1):
        (x, y), (nx, ny) = path[i], path[i + 1]
        put(x, y, d[(nx - x, ny - y)])
    # last cell keeps direction of the final step
    (px, py), (lx, ly) = path[-2], path[-1]
    put(lx, ly, d[(lx - px, ly - py)])

# main room x0..4 y0..4, interior x1..3 y1..3
room(0, 0, 4, 4)
# man: @ start facing east
# (1,1)=@ -> (2,1)='5' A=5 -> (3,1)='v' -> (3,2)='<' -> (2,2)='s' send self pipe
# -> (1,2)='v' -> (1,3)='>' -> (2,3)='r' receive -> (3,3)='^' -> (3,2)... loop
put(1, 1, '@'); put(2, 1, '5'); put(3, 1, 'v')
put(3, 2, '<'); put(2, 2, 's'); put(1, 2, 'v')
put(1, 3, '>'); put(2, 3, 'r'); put(3, 3, 'H')

# output room
room(9, 6, 11, 8); put(10, 7, 'O')

# self pipe: main south wall -> around -> main east wall
pipe([(2, 5), (2, 6), (3, 6), (4, 6), (5, 6), (6, 6), (6, 5), (6, 4), (6, 3), (6, 2), (5, 2)])

out = '\n'.join(''.join(r).rstrip() for r in g) + '\n'
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'selfpipe.man'), 'w').write(out)
print('ok')
