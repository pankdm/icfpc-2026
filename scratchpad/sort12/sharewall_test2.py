#!/usr/bin/env python3
"""Functional shared-wall probe.  Room A (top) and room B (bottom) share a wall.
A pipe runs A -> B around the outside.  If the parser MERGES the two rooms, the
pipe becomes a self-loop and the load fails -> shared walls do not work.
Room B forwards to an output room.  Expected output: 7.
"""
import os
from sharewall_test import G

HERE = os.path.dirname(os.path.abspath(__file__))


def expand(pts):
    out = [pts[0]]
    for (x, y) in pts[1:]:
        cx, cy = out[-1]
        dx = (x > cx) - (x < cx)
        dy = (y > cy) - (y < cy)
        while (cx, cy) != (x, y):
            cx += dx; cy += dy
            out.append((cx, cy))
    return out


def build(share):
    yb = 4 if share else 5
    g = G(18, 14)
    g.room(0, 0, 5, 4)
    g.room(0, yb, 5, yb + 4, force=share)
    g.put(1, 1, '@'); g.put(2, 1, '7'); g.put(3, 1, 's'); g.put(4, 1, 'H')
    g.put(1, yb + 1, '@'); g.put(2, yb + 1, 'r'); g.put(3, yb + 1, 's')
    g.put(4, yb + 1, 'H')
    g.room(10, yb + 1, 12, yb + 3); g.put(11, yb + 2, 'O')
    g.pipe(expand([(6, 2), (7, 2), (7, yb + 2), (6, yb + 2)]))
    g.pipe(expand([(6, yb + 3), (8, yb + 3), (8, yb + 2), (9, yb + 2)]))
    return g


if __name__ == '__main__':
    for share in (True, False):
        g = build(share)
        open(os.path.join(HERE, 'share2_%s.man' % ('yes' if share else 'no')), 'w').write(g.text())
    print('ok')
