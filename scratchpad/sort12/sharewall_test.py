#!/usr/bin/env python3
"""Probe: can two rooms share a wall line?  Variants:
  A: rooms side by side sharing a full column, corners aligned  (x0..4 and x4..8)
  B: rooms stacked sharing a full row, corners aligned
  C: small room's corner '+' lands mid-wall of the big room
Each writes a .man that reads a value and echoes it, so a load error is visible.
"""
import os, sys

D = {(1, 0): '>', (-1, 0): '<', (0, 1): 'v', (0, -1): '^'}
HERE = os.path.dirname(os.path.abspath(__file__))


class G:
    def __init__(s, w, h):
        s.w, s.h = w, h
        s.g = [[' '] * w for _ in range(h)]

    def put(s, x, y, ch, force=False):
        if not (0 <= x < s.w and 0 <= y < s.h):
            raise SystemExit("oob (%d,%d)" % (x, y))
        if s.g[y][x] != ' ' and not force:
            raise SystemExit("collision (%d,%d) %r vs %r" % (x, y, s.g[y][x], ch))
        s.g[y][x] = ch

    def room(s, x0, y0, x1, y1, force=False):
        for x in range(x0, x1 + 1):
            s.put(x, y0, '-' if x0 < x < x1 else '+', force)
            s.put(x, y1, '-' if x0 < x < x1 else '+', force)
        for y in range(y0 + 1, y1):
            s.put(x0, y, '|', force); s.put(x1, y, '|', force)

    def pipe(s, path):
        for i in range(len(path) - 1):
            (x, y), (nx, ny) = path[i], path[i + 1]
            s.put(x, y, D[(nx - x, ny - y)])
        (px, py), (lx, ly) = path[-2], path[-1]
        s.put(lx, ly, D[(lx - px, ly - py)])

    def text(s):
        return '\n'.join(''.join(r).rstrip() for r in s.g) + '\n'


def variant_a():
    """two rooms sharing column 4; A: x0..4, B: x4..8"""
    g = G(16, 10)
    g.room(0, 0, 4, 4)
    g.room(4, 0, 8, 4, force=True)
    return g


def variant_b():
    """two rooms sharing row 4"""
    g = G(16, 12)
    g.room(0, 0, 6, 4)
    g.room(0, 4, 6, 8, force=True)
    return g


def variant_c():
    """small room's corners land mid-wall of the big room"""
    g = G(16, 12)
    g.room(0, 0, 9, 4)
    g.room(2, 4, 6, 8, force=True)
    return g


if __name__ == '__main__':
    for name, fn in (('a', variant_a), ('b', variant_b), ('c', variant_c)):
        g = fn()
        open(os.path.join(HERE, 'share_%s.man' % name), 'w').write(g.text())
    print('ok')
