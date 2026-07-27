#!/usr/bin/env python3
"""Where do the forced newlines come from? Count port->port reversals by pair."""
import sys, os, json
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
S4 = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(S4, 'tools'))
sys.path.insert(0, os.path.join(S4, 'solutions', 'little-little-man'))
import boustro
from llm_eval import get_flow, GLYPH

BASE = {'ri': 55, 'sp': 65, 'rp': 75, 'sc': 95, 'rr': 119, 'sd': 125,
        'sa': 163, 'ss': 225, 'cc': 245, 'cr': 275}


def main(cols):
    flow = get_flow()
    bands = {}
    bands.update(boustro.voronoi_bands(
        [(n, c) for n, c in cols.items() if GLYPH[n] == 's']))
    bands.update(boustro.voronoi_bands(
        [(n, c) for n, c in cols.items() if GLYPH[n] == 'r']))
    nb = 0
    lits = 0
    ops = 0
    pairs = Counter()
    oneway = {'sd', 'sa', 'ss'}
    for label, tokens in flow.blocks.items():
        prev = None
        prev_hi = None
        for tok in tokens:
            if isinstance(tok, tuple):
                break
            ops += 1
            if len(tok) > 1 and tok[0] == '`':
                lits += 1
            if tok in cols:
                lo, hi = bands[tok]
                if prev is not None and lo < prev_lo:
                    nb += 1
                    pairs[(prev, tok)] += 1
                prev, prev_lo = tok, lo
    print('ops', ops, 'literals', lits, 'reversals', nb)
    tot_ow = sum(v for k, v in pairs.items()
                 if k[0] in oneway and k[1] in oneway)
    print('reversals both one-way (display):', tot_ow)
    for k, v in pairs.most_common(20):
        print(f'  {k[0]}->{k[1]:3s} {v}')


if __name__ == '__main__':
    cols = json.loads(sys.argv[1]) if len(sys.argv) > 1 else BASE
    main(cols)
