#!/usr/bin/env python3
"""Sweep build_ring's champion layout over widths; report footprints only."""
import os
import sys
import traceback

HL = "/Users/visenbaev/icfpc26/solutions/history-lesson"
sys.path.insert(0, HL)
os.chdir(HL)
import build_ring as BR

lo = int(sys.argv[1]) if len(sys.argv) > 1 else 74
hi = int(sys.argv[2]) if len(sys.argv) > 2 else 86
for W in range(lo, hi + 1):
    for tag, kw in (("west_first", dict(variable=True, compact_tail=True,
                                        west_first=True)),
                    ("compact", dict(variable=True, compact_tail=True))):
        try:
            p = BR.build(W, **kw)
            w, h, s = p.footprint()
            print("W=%d %-10s -> %dx%d score %d" % (W, tag, w, h, s))
        except Exception as e:
            msg = str(e).splitlines()[0] if str(e) else type(e).__name__
            print("W=%d %-10s -> FAIL %s" % (W, tag, msg[:70]))
