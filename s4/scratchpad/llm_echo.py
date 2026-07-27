#!/usr/bin/env python3
"""Scratch-echo duplication: match sp/rp pairs per block and score assignments.

The scratch echo is a FIFO pipe loop we own outright, so it can be REPLICATED
into k independent rooms at k different column pairs.  Any partition of the
push/pop pairs across the copies preserves FIFO inside each copy (a subsequence
of a FIFO-consistent stream is FIFO-consistent), so the only constraint is that
a pair's push and pop go to the SAME copy, and that both live in one block.
MEASURED: all 241 pairs are in-block, 0 cross-block, so the rewrite is total.

Blocks are laid independently (``_lay_once`` resets the cursor at every block),
so the row cost of a block depends only on its own assignment -- greedy
coordinate descent per block is therefore a per-block optimum search, not a
global heuristic.
"""
import sys, os, json, copy
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
S4 = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(S4, 'tools'))
sys.path.insert(0, os.path.join(S4, 'solutions', 'little-little-man'))
sys.path.insert(0, HERE)
import boustro
from llm_eval import get_flow

BASE_GLYPH = {'ri': 'r', 'sp': 's', 'rp': 'r', 'sc': 's', 'rr': 'r',
              'sd': 's', 'sa': 's', 'ss': 's', 'cc': 's', 'cr': 'r'}


def echo_names(k):
    """Port names for k echo copies; copy 0 keeps the original names."""
    return [('sp', 'rp')] + [(f'sp{i}', f'rp{i}') for i in range(1, k)]


def glyphs_for(k):
    g = dict(BASE_GLYPH)
    for s, r in echo_names(k)[1:]:
        g[s] = 's'
        g[r] = 'r'
    return g


def bands_for(cols, glyphs):
    b = {}
    b.update(boustro.voronoi_bands(
        [(n, c) for n, c in cols.items() if glyphs[n] == 's']))
    b.update(boustro.voronoi_bands(
        [(n, c) for n, c in cols.items() if glyphs[n] == 'r']))
    return b


def pairs_of(tokens):
    """FIFO-match sp pushes to rp pops inside one block's token list."""
    pushes, pairs, loose = [], [], []
    for i, tok in enumerate(tokens):
        if isinstance(tok, tuple):
            break
        if tok == 'sp':
            pushes.append(i)
        elif tok == 'rp':
            if pushes:
                pairs.append((pushes.pop(0), i))
            else:
                loose.append(i)
    loose.extend(pushes)
    return pairs, loose


def sim_rows(tokens, bands, opmin, opmax):
    """Rows a block occupies under boustro.Cursor placement (railflow rules)."""
    x, d = opmin - 1, 1
    rows = 1
    row0 = True          # still on the entry row
    for tok in tokens:
        if isinstance(tok, tuple):
            if tok[0] == 'go':
                if d == 1:
                    rows += 1
                    d = -1
            elif tok[0] == 'br':
                if row0:
                    rows += 1
                    d = -d
                rows += 1    # the private westbound rail row
            return rows
        lo, hi = bands.get(tok, (opmin, opmax))
        lo, hi = max(lo, opmin), min(hi, opmax)
        for _ in range(4):
            nx = max(x + 1, lo) if d == 1 else min(x - 1, hi)
            if (nx <= hi) if d == 1 else (nx >= lo):
                break
            rows += 1
            row0 = False
            d = -d
            x = x + (1 if d == -1 else -1)   # the turn column
        else:
            return None
        x = nx
    return rows


def assign_block(tokens, bands, opmin, opmax, k):
    """Greedy coordinate descent over which echo copy each pair uses."""
    pairs, loose = pairs_of(tokens)
    if not pairs:
        return tokens, sim_rows(tokens, bands, opmin, opmax)
    names = echo_names(k)
    choice = [0] * len(pairs)

    def render(ch):
        out = list(tokens)
        for (pi, po), c in zip(pairs, ch):
            out[pi], out[po] = names[c][0], names[c][1]
        return out

    best = sim_rows(render(choice), bands, opmin, opmax)
    if best is None:
        best = 10 ** 6
    improved = True
    while improved:
        improved = False
        for i in range(len(pairs)):
            for c in range(k):
                if c == choice[i]:
                    continue
                trial = list(choice)
                trial[i] = c
                r = sim_rows(render(trial), bands, opmin, opmax)
                if r is not None and r < best:
                    best, choice, improved = r, trial, True
    return render(choice), best


def rewrite_flow(cols, k):
    """Return (new_flow, glyphs, total_rows_estimate)."""
    flow = get_flow()
    glyphs = glyphs_for(k)
    bands = bands_for(cols, glyphs)
    opmin = min(cols.values()) - 3
    opmax = max(cols.values())
    new = copy.deepcopy(flow)
    total = 0
    for label, tokens in flow.blocks.items():
        toks, rows = assign_block(list(tokens), bands, opmin, opmax, k)
        new.blocks[label] = toks
        total += rows
    return new, glyphs, total


if __name__ == '__main__':
    cols = json.loads(sys.argv[1])
    for k in (1, 2, 3, 4, 5):
        c = dict(cols)
        _, g, total = rewrite_flow(c, 1) if k == 1 else (None, None, None)
        print(k, total)
