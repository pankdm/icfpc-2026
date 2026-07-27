#!/usr/bin/env python3
"""Hand-placed arm8 build: 8-tick greater arm, 10-tick less/equal, 16-tick lap chain.

Loop at ux=5, uy=2 (interior rows 1..3):
  row1  >  >  +  s  d  | m0
  row2  ^  X  -  m  U  a
  row3     >  +  W  s  ^ (gate)
Lap chain: m0 -> col7 descent -> q -> Y -> (main east copy) -> test -> m R M -> gate.
Round chain: test straight -> R n, b, m, R -> row4 east -> M (shared) -> gate.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from arm8 import OUTER, render

CELLS = {
    # ---- compare loop (ux=5, uy=2)
    (1, 1): '>', (2, 1): '>', (3, 1): '+', (4, 1): 's', (5, 1): 'd',
    (1, 2): '^', (2, 2): 'X', (3, 2): '-', (4, 2): 'm', (5, 2): 'U', (6, 2): 'a',
    (2, 3): '>', (3, 3): '+', (4, 3): 'W', (5, 3): 's', (6, 3): '^',
    # ---- lap-end merge + chain
    (6, 1): '>', (7, 1): 'v', (7, 5): 'q', (7, 6): 'Y',
    (8, 6): 'v', (8, 7): '<', (7, 7): '@',
    (6, 7): 'd', (6, 6): 'm', (6, 5): 'R', (6, 4): 'M',
    # ---- output man (born west of Y, walks west along row 6)
    (5, 6): 'W', (3, 6): 's', (2, 6): 'H',
    # ---- round chain
    (5, 7): 'R', (4, 7): 'b', (3, 7): 'm', (2, 7): 'R', (1, 7): '^',
    (1, 4): '>', (8, 4): '^', (8, 3): '<',
}

g = dict(OUTER)
for k, v in CELLS.items():
    if k in g:
        raise SystemExit("collision at %r" % (k,))
    g[k] = v

dest = sys.argv[1] if len(sys.argv) > 1 else "/tmp/arm8_hand.man"
open(dest, "w").write(render(g))
print("wrote", dest)
