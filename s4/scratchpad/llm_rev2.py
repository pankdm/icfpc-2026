#!/usr/bin/env python3
"""Reversal profile AFTER the echo split, to pick the next duplication target."""
import sys, os, json
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'tools'))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'solutions',
                                'little-little-man'))
import echo_split
from llm_eval import get_flow

EM4 = {"ri": 112, "sp": 118, "rp": 134, "sc": 176, "rr": 243, "sd": 326,
       "sa": 336, "ss": 346, "cc": 352, "cr": 386, "sp1": 316, "rp1": 323}


def main(cols, k):
    flow, glyphs, est = echo_split.rewrite_flow(get_flow(), cols, k, opmin=50)
    bands = echo_split.bands_for(cols, glyphs)
    opmin, opmax = 50, max(cols.values())
    pairs = Counter()
    n = 0
    for label, tokens in flow.blocks.items():
        x, d = opmin - 1, 1
        prev = None
        for tok in tokens:
            if isinstance(tok, tuple):
                break
            lo, hi = bands.get(tok, (opmin, opmax))
            lo, hi = max(lo, opmin), min(hi, opmax)
            turned = False
            for _ in range(4):
                nx = max(x + 1, lo) if d == 1 else min(x - 1, hi)
                if (nx <= hi) if d == 1 else (nx >= lo):
                    break
                turned = True
                d = -d
                x = x + (1 if d == -1 else -1)
            if turned and prev is not None:
                pairs[(prev, tok)] += 1
                n += 1
            x = nx
            if tok in cols:
                prev = tok
    print('reversals', n, 'est rows', est)
    for kk, v in pairs.most_common(14):
        print(f'  {kk[0]:4s}->{kk[1]:4s} {v}')


if __name__ == '__main__':
    cols = json.loads(sys.argv[1]) if len(sys.argv) > 1 else EM4
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    main(cols, k)
