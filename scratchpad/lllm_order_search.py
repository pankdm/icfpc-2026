#!/usr/bin/env python3
"""Anneal the holder COLUMN ORDER to minimise controller rows.

Rows are the box driver: width is order-invariant (165), so box = max(w,h)^2 is
minimised by minimising the ribbon-wrap count, which is a pure function of the
order in which port columns are visited.
"""
import os, sys, random, json
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "solutions", "little-little-little-man"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import build_lllm as B


def rows(order):
    try:
        return B.measure_order(list(order))[0]
    except Exception:
        return 10 ** 6


def anneal(seed, iters=20000):
    rng = random.Random(seed)
    cur = list(B.HOLDER_ORDER)
    rng.shuffle(cur)
    cc = rows(cur)
    best, bc = list(cur), cc
    T0, T1 = 12.0, 0.05
    n = len(cur)
    for it in range(iters):
        T = T0 * (T1 / T0) ** (it / iters)
        cand = list(cur)
        m = rng.random()
        if m < 0.55:                      # swap two
            i, j = rng.randrange(n), rng.randrange(n)
            cand[i], cand[j] = cand[j], cand[i]
        elif m < 0.85:                    # move one
            i = rng.randrange(n); j = rng.randrange(n)
            cand.insert(j, cand.pop(i))
        else:                             # reverse a span
            i, j = sorted((rng.randrange(n), rng.randrange(n)))
            cand[i:j + 1] = reversed(cand[i:j + 1])
        c = rows(cand)
        if c <= cc or rng.random() < pow(2.718281828, -(c - cc) / T):
            cur, cc = cand, c
            if c < bc:
                best, bc = list(cand), c
    return bc, best


def main():
    seeds = list(range(int(sys.argv[1]) if len(sys.argv) > 1 else 24))
    print("baseline current order rows=%d" % rows(B.HOLDER_ORDER))
    best, bo = 10 ** 9, None
    with ProcessPoolExecutor() as ex:
        for c, o in ex.map(anneal, seeds):
            if c < best:
                best, bo = c, o
                print("  rows=%d  %s" % (c, o), flush=True)
    print("BEST rows=%d" % best)
    print(json.dumps(bo))
    with open(os.path.join(HERE, "lllm_best_order.json"), "w") as f:
        json.dump({"rows": best, "order": bo}, f, indent=1)


if __name__ == "__main__":
    main()
