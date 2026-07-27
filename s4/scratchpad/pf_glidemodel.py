#!/usr/bin/env python3
"""Static glide proxy: total |dx| the controller man walks per pass over the
op stream, for a given port map.

45% of pathfinder's ticks are the man gliding over blank controller cells
(measured: 505,431 of 1,115,997 on `there and back again`), and that cost is
exactly the sum of |dx| between consecutive op placements.  Box alone cannot
rank two layouts because a narrower controller can be worth more in ticks than
it costs in rows.

  cd s4 && python3 scratchpad/pf_glidemodel.py '{"ri":10,...}'
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))

import pf_bandsearch as m  # noqa: E402
import boustro  # noqa: E402

_orig_place = boustro.Cursor.place
_orig_run = boustro.Cursor.place_run
_orig_put = boustro.Cursor.put


def measure(cols):
    total = [0, None]

    def place(self, ch, lo, hi):
        _orig_place(self, ch, lo, hi)
        if total[1] is not None:
            total[0] += abs(self.x - total[1])
        total[1] = self.x

    def place_run(self, chars, lo, hi):
        _orig_run(self, chars, lo, hi)
        if total[1] is not None:
            total[0] += abs(self.x - total[1])
        total[1] = self.x

    boustro.Cursor.place = place
    boustro.Cursor.place_run = place_run
    try:
        rows, width = m.geometry(cols, 0, m.FORBID)
    finally:
        boustro.Cursor.place = _orig_place
        boustro.Cursor.place_run = _orig_run
    return rows, width, total[0]


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        cols = dict(m.BASE)
        cols.update(json.loads(arg))
        rows, width, glide = measure(cols)
        print(f"rows {rows} width {width} static-glide {glide:,}")
