#!/usr/bin/env python3
"""Search the split/pad commit ORDER of railflow's fixpoint.

Both formulations fail in opposite directions (all-at-once over-pays, one-at-a-
time can stall), so try: all, topmost, bottom-most, and randomized restarts.
"""
import sys, os, random, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'tools'))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'solutions',
                                'little-little-man'))
import boustro, railflow, echo_split
from llm_eval import get_flow

EM4 = {"ri": 112, "sp": 118, "rp": 134, "sc": 176, "rr": 243, "sd": 326,
       "sa": 336, "ss": 346, "cc": 352, "cr": 386, "sp1": 316, "rp1": 323}


def rows(flow, glyphs, bands, pick_split, pick_pad, nrail=48):
    try:
        cursor, entry, cells, nr, intent = railflow.solve(
            flow, list(flow.blocks), EM4, glyphs, bands, 0, 0, nrail,
            max(EM4.values()), (), 80, pick_split, pick_pad)
    except boustro.Conflict:
        return None, None
    return max(y for _, y in cursor.cells) + 2, nr


def main(n):
    base = get_flow()
    flow, glyphs, _ = echo_split.rewrite_flow(base, EM4, 2, opmin=50)
    bands = echo_split.bands_for(EM4, glyphs)
    strats = {
        'all/all':       (lambda f: f, None),
        'top/all':       (lambda f: f[:1], None),
        'bottom/all':    (lambda f: f[-1:], None),
        'top/top':       (lambda f: f[:1], lambda f: f[:1]),
        'all/top':       (lambda f: f, lambda f: f[:1]),
        'half/all':      (lambda f: f[:max(1, len(f) // 2)], None),
    }
    best = (10 ** 9, None)
    for name, (ps, pp) in strats.items():
        h, nr = rows(flow, glyphs, bands, ps, pp)
        print(f'{name:12s} rows {h} nrail {nr}', flush=True)
        if h and h < best[0]:
            best = (h, name)
    rng = random.Random(0)
    for i in range(n):
        k = rng.choice([1, 1, 1, 2, 3])
        ps = lambda f, k=k, rng=rng: rng.sample(f, min(k, len(f)))
        pp = rng.choice([None, lambda f: f[:1]])
        h, nr = rows(flow, glyphs, bands, ps, pp)
        if h and h < best[0]:
            best = (h, f'rand#{i} k={k}')
            print(f'rand#{i} rows {h} nrail {nr}', flush=True)
    print('BEST', best)


if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 40)
