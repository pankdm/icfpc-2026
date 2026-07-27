#!/usr/bin/env python3
"""How few controller rows can pathfinder's op stream take, at any width?

Same fast model as pf_bandsearch, but the objective is rows alone (width is
capped by --maxw).  Tells us whether 191 rows is the geometry floor or just the
best point on the box trade-off curve.

    cd s4 && python3 scratchpad/pf_minrows.py --maxw 320
"""
import argparse
import random
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE))
import pf_bandsearch as m  # noqa: E402
from boustro import Conflict  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--maxw", type=int, default=320)
    ap.add_argument("--iters", type=int, default=30000)
    ap.add_argument("--seed", type=int, default=5)
    args = ap.parse_args()
    rnd = random.Random(args.seed)

    def cost(cols):
        try:
            r, w = m.geometry(cols, 0, m.FORBID)
        except Conflict:
            return None
        if w > args.maxw:
            return None
        return (r, w)

    cols = dict(m.BASE)
    cur = cost(cols)
    best = (cur, dict(cols))
    for it in range(args.iters):
        cand = dict(cols)
        for _ in range(rnd.choice([1, 1, 2, 3])):
            n = rnd.choice(m.PORTS)
            cand[n] = max(1, min(args.maxw - 4, cand[n] + rnd.choice(
                [-32, -16, -8, -4, -2, -1, 1, 2, 4, 8, 16, 32,
                 rnd.randint(-80, 80)])))
        if len(set(cand.values())) != len(cand):
            continue
        got = cost(cand)
        if got is None:
            continue
        if got <= cur:
            cols, cur = cand, got
            if got < best[0]:
                best = (got, dict(cand))
    print(f"maxw {args.maxw}: rows {best[0][0]} width {best[0][1]}")
    print("  cols =", dict(sorted(best[1].items(), key=lambda kv: kv[1])))


if __name__ == "__main__":
    main()
