#!/usr/bin/env python3
"""Render each mm2 room on its own so the glyph map can be eyeballed."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'solutions', 'matmul'))
from mm2lib import Grid
import mm2rooms as R

for name in ['mul', 'crel', 'arel', 'brel', 'spl', 'pcnt', 'acc']:
    if len(sys.argv) > 1 and name not in sys.argv[1:]:
        continue
    g = Grid()
    try:
        room = getattr(R, name)(g, 0, 0)
    except Exception as e:
        print(f"--- {name}: ERROR {e}")
        continue
    print(f"--- {name}  {room.w}x{room.h}  pipes={ {k: v for k, v in room.pipes.items()} }")
    txt = g.render().split('\n')
    for i, line in enumerate(txt):
        print(f"{i:2d} {line}")
    print()
