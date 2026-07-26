#!/usr/bin/env python3
"""Anneal the two free permutations of the LLLM layout against cost_model.py.

    python3 solutions/little-little-little-man/search_layout.py [--iters N] [--what both]

WHAT IS FREE.  Two orderings do not change a single instruction:

  HOLDER ORDER  which holder room gets which controller column.  The man walks
                between port columns, so putting holders that are used together
                next to each other is pure profit.
  BLOCK ORDER   which block is laid out under which.  `go` to the NEXT block is
                a 2-cell descend; every other edge pays a west run to a highway
                lane, the ride, and the glide back east.  So the hottest
                successor of each block wants to be the block right below it.
  HOLDER FLIP   which of a holder room's two interior columns carries the DROP
                pipe.  `get(h)` is `hr` then `hw`, so with the drop always on
                the left EVERY get() on a westward ribbon row asks for a column
                behind the cursor and costs a whole wrap row -- and 197 of the
                388 controller rows are wraps.

Both were previously searched on ROW COUNT alone, which is why the last attempt
graded 27% worse on ticks (see the HOLDER_ORDER comment in build_lllm.py).  The
objective here is the real one, max(w, h)^2 * ticks, with ticks from the exact
model -- 4 ms per candidate instead of a 55 s grade.
"""
import argparse
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))

import build_lllm as B
import cost_model as CM
import lllm_flow as F
import lllm_sim as SIM

# rows of chrome above and below the controller (device band, pipes, display).
# Measured: footprint height - placer.y = 32 for the two-tier band.
CHROME_ROWS = 32


class Objective(object):
    def __init__(self):
        self.hits = CM.all_hits()
        self.flow = F.build_flow()
        self.base = B.split_blocks(self.flow)
        self.by_label = dict(self.base)
        self.heat = SIM.block_heat()
        self.cache = {}

    def blocks_for(self, order):
        return [(l, self.by_label[l]) for l in order]

    def __call__(self, holder_order, block_order, flip=(), rounds=2):
        key = (tuple(holder_order), tuple(block_order), tuple(sorted(flip)), rounds)
        hit = self.cache.get(key)
        if hit is not None:
            return hit
        try:
            placer, cols = CM.placer_costs(holder_order=list(holder_order),
                                           blocks=self.blocks_for(block_order),
                                           heat=self.heat, flip=tuple(flip),
                                           rounds=rounds)
            t = CM.avg_ticks(self.hits, placer)
            h = placer.y + CHROME_ROWS
            box = max(cols.width, h) ** 2
            val = (box * t, box, t)
        except Exception:                      # an illegal order simply loses
            val = (float("inf"), 0, 0)
        self.cache[key] = val
        return val


def anneal(obj, holder_order, block_order, flip, iters, seed, what, out=None):
    rng = random.Random(seed)
    cur_h, cur_b, cur_f = list(holder_order), list(block_order), set(flip)
    cur = obj(cur_h, cur_b, cur_f)
    best, best_h, best_b, best_f = cur, list(cur_h), list(cur_b), set(cur_f)
    # T is a FRACTION of the current score: a typical single-move delta here is
    # a few tenths of a percent, so 0.06 accepted everything and the search was
    # a random walk that never beat its own start.
    T0, T1 = 0.0015, 0.00005
    for it in range(iters):
        T = T0 * (T1 / T0) ** (it / float(iters))
        ch, cb, cf = list(cur_h), list(cur_b), set(cur_f)
        move = what if what != "both" else rng.choice(("holder", "block", "flip"))
        if move == "flip":
            cf.symmetric_difference_update({rng.choice(ch)})
        elif move == "holder":
            i, j = rng.randrange(len(ch)), rng.randrange(len(ch))
            if rng.random() < 0.5:
                ch[i], ch[j] = ch[j], ch[i]
            else:
                v = ch.pop(i)
                ch.insert(j, v)
        else:
            # block 0 is the entry point ('@'), it must stay first
            i = rng.randrange(1, len(cb))
            j = rng.randrange(1, len(cb))
            v = cb.pop(i)
            cb.insert(j, v)
        cand = obj(ch, cb, cf)
        if cand[0] == float("inf"):
            continue
        if cand[0] < cur[0] or rng.random() < pow(2.718281828,
                                                  -(cand[0] - cur[0]) / (T * cur[0])):
            cur, cur_h, cur_b, cur_f = cand, ch, cb, cf
            if cand[0] < best[0]:
                best, best_h, best_b, best_f = cand, list(ch), list(cb), set(cf)
                if out:
                    # checkpoint every improvement: a long anneal is worth
                    # harvesting before it finishes
                    json.dump({"score": best[0], "box": best[1], "ticks": best[2],
                               "holder": best_h, "block": best_b,
                               "flip": sorted(best_f)},
                              open(out, "w"), indent=1)
    return best, best_h, best_b, best_f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=20000)
    ap.add_argument("--restarts", type=int, default=4)
    ap.add_argument("--what", default="both",
                    choices=("holder", "block", "flip", "both"))
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default=None,
                    help="JSON file rewritten on every improvement")
    args = ap.parse_args()

    obj = Objective()
    h0 = [h for h in B.HOLDER_ORDER if h in F.HOLDERS]
    b0 = list(B.BLOCK_ORDER) or [l for l, _t in obj.base]
    f0 = list(B.HOLDER_FLIP)
    start = obj(h0, b0, f0)
    print("start   score=%.4g box=%d ticks=%.0f" % start, flush=True)

    best, bh, bb, bf = start, h0, b0, f0
    for r in range(args.restarts):
        s, h, b, f = anneal(obj, bh, bb, bf, args.iters, args.seed + r, args.what,
                            out=args.out)
        print("run %-2d  score=%.4g box=%d ticks=%.0f" % ((r,) + s), flush=True)
        if s[0] < best[0]:
            best, bh, bb, bf = s, h, b, f
    best = obj(bh, bb, bf, rounds=6)      # re-score the winner at the fixpoint
    start = obj(h0, b0, f0, rounds=6)
    print("\nbest    score=%.4g box=%d ticks=%.0f  (%.3fx ticks, %.3fx score)"
          % (best + (start[2] / best[2], start[0] / best[0])))
    print("\nHOLDER_ORDER = [")
    for i in range(0, len(bh), 5):
        print("    " + ", ".join('"%s"' % x for x in bh[i:i + 5]) + ",")
    print("]")
    print("\nBLOCK_ORDER = [")
    for i in range(0, len(bb), 4):
        print("    " + ", ".join('"%s"' % x for x in bb[i:i + 4]) + ",")
    print("]")
    print("\nHOLDER_FLIP = %r" % sorted(bf))


if __name__ == "__main__":
    main()
