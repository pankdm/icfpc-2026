#!/usr/bin/env python3
"""Enumerate swar_build's (L, k, W) geometry space and report the BOX floor.

geometry() minimises box x ticks; this asks the different question -- what is the
smallest achievable box, and at what tick cost -- and also sweeps the "floor"
constants GAP / SWAP_ROWS / SPACER that the builder's comments call fixed.

  python3 scratchpad/plot3/enum.py
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SOL = os.path.join(os.path.dirname(os.path.dirname(HERE)), "icfpc26", "solutions", "plotter")
SOL = "/Users/visenbaev/icfpc26/solutions/plotter"
sys.path.insert(0, SOL)
sys.path.insert(0, "/Users/visenbaev/icfpc26/tools")

import swar_build as B
import swar_setup as SS

pre, px, py, tail_body, tail_fin = SS.segments()
BW = max(len(px), len(py)) + 2
npre, ntail = len(pre), len(tail_body)
print("npre=%d ntail=%d BW=%d  BASE_TICKS=%d" % (npre, ntail, BW, B.BASE_TICKS))
print("current: GAP=%d SWAP_ROWS=%d SPACER=%d vfixed=%d" % (B.GAP, B.SWAP_ROWS, B.SPACER, B.vfixed()))

rows = []
for gap in (2, 3):
    for swap in (1, 2):
        for spacer in (0,):
            vf = 34 + gap + swap
            for L in range(3, 24):
                IH = L + 7 + spacer
                if IH > 2 * L + 2:
                    continue
                for k in range(3, L - 1, 2):
                    trows = L - k - 1
                    if trows < 1:
                        continue
                    for W in range(BW + 8, 90):
                        pre_cap = (W - 3) + (k - 1) * (W - BW - 3) + (W - BW - 2)
                        tail_cap = trows * (W - 3)
                        if pre_cap < npre or tail_cap < ntail:
                            continue
                        pad = pre_cap - npre + (0 if trows < 2 else (tail_cap - ntail) % 2)
                        w, h = W + 2, IH + vf
                        rows.append((max(w, h) ** 2, max(w, h) ** 2 * (B.BASE_TICKS + pad),
                                     gap, swap, L, k, W, w, h, pad))
                        break

rows.sort()
print("\nsmallest boxes:")
seen = set()
for box, score, gap, swap, L, k, W, w, h, pad in rows:
    key = (box, gap, swap)
    if key in seen:
        continue
    seen.add(key)
    print("  box %4d (%2dx%2d)  gap=%d swap=%d L=%2d k=%d W=%2d pad=%3d  est.score %d"
          % (box, w, h, gap, swap, L, k, W, pad, score))
    if len(seen) > 14:
        break
