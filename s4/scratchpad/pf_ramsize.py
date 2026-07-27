#!/usr/bin/env python3
"""Footprint of split_ram for a range of (size, belts)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FORK = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(FORK, "tools"))

import littleman as lm  # noqa: E402
import split_ram  # noqa: E402

for size, belts in [(32, 2), (32, 3), (32, 4), (32, 5), (32, 6), (32, 8),
                    (32, 9), (32, 16), (256, 6), (256, 8), (256, 9),
                    (256, 12), (256, 16)]:
    p = lm.Program()
    try:
        info = split_ram.build(p, 0, 0, size, belts)
    except Exception as exc:
        print(size, belts, "FAIL", exc)
        continue
    x0, y0, x1, y1 = p.bounds()
    print(f"size {size:4d} belts {belts:3d}  span x {x0}..{x1} ({x1-x0+1}) "
          f"y {y0}..{y1} ({y1-y0+1})  cmd {info['command']} reply {info['reply']}")
