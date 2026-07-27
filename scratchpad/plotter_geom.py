#!/usr/bin/env python3
"""Enumerate plotter swar geometry candidates (L, k, W, IH) and rank them."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PL = "/tmp/plwt/solutions/plotter"
sys.path.insert(0, PL)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
sys.path.insert(0, os.path.join(HERE, ".."))

import swar_setup as SS  # noqa: E402

BASE_TICKS = 505
SPACER = 0


def main():
    pre, px, py, tail_body, tail_fin = SS.segments()
    pass
    BW = max(len(px), len(py)) + 2
    npre, ntail = len(pre), len(tail_body)
    print(f"npre={npre} ntail={ntail} BW={BW}")

    cands = []
    for L in range(4, 20):
        IH = L + 7 + SPACER
        if IH > 2 * L + 2:
            continue
        h = IH + 39 - (1 - SPACER)
        for k in range(1, L - 1):
            if k % 2 != 1:
                continue
            trows = L - k - 1
            if trows < 1:
                continue
            for W in range(BW + 8, 90):
                pre_cap = (W - 3) + (k - 1) * (W - BW - 3) + (W - BW - 2)
                tail_cap = trows * (W - 3)
                if pre_cap < npre or tail_cap < ntail:
                    continue
                pad = pre_cap - npre + (0 if trows < 2 else (tail_cap - ntail) % 2)
                w = W + 2
                box = max(w, h) ** 2
                cands.append((box * (BASE_TICKS + pad), box, w, h, L, k, W, IH, pad))
                break
    cands.sort()
    print(f"{'model':>12} {'box':>6} {'w':>3} {'h':>3} {'L':>2} {'k':>2} "
          f"{'W':>3} {'IH':>3} {'pad':>4}")
    for c in cands[:25]:
        print(f"{c[0]:>12} {c[1]:>6} {c[2]:>3} {c[3]:>3} {c[4]:>2} {c[5]:>2} "
              f"{c[6]:>3} {c[7]:>3} {c[8]:>4}")


if __name__ == "__main__":
    main()
