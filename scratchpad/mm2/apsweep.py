"""Measure: what box does the mm2i floor plan reach if the A band shrinks?

Pure geometry probe -- the grid it builds is NOT correct (a short A queue
deadlocks), we only want footprint vs ap_rect.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'solutions', 'matmul'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import build_mm2h as B  # noqa: E402

for w, h in [(15, 18), (13, 16), (11, 14), (9, 12), (7, 10), (6, 9), (5, 8), (4, 7),
             (3, 6), (2, 5), (1, 4)]:
    try:
        g, n_ap, n_br = B.build(ap_rect=(2, 2, w, h, False))
        fw, fh, box = g.footprint()
        print(f"band {w:2d}x{h:2d} = {w*h:3d} -> {fw}x{fh} box {box}  AP={n_ap}")
    except Exception as e:
        print(f"band {w:2d}x{h:2d} = {w*h:3d} -> FAIL {type(e).__name__}: {str(e)[:70]}")
