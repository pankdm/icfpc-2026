#!/usr/bin/env python3
"""Replicate the scratch echo across k rooms and re-assign every push/pop pair.

WHY.  The LLM controller's height is dominated by *forced newlines*: the
boustrophedon cursor must start a new row whenever the next port op's
nearest-pipe band lies behind it.  Measured on the 832-row rail controller,
508 of those reversals exist and **334 of them target the scratch echo**
(`sp` push / `rp` pop) -- only 5 involve the one-way display ports.

The echo is a FIFO pipe loop we own outright, so unlike the RAM or the display
it can simply be *replicated*: k identical `@>rsv` rooms at k different column
pairs.  A pair's push and pop must land on the same copy; beyond that any
partition is legal, because a subsequence of a FIFO-consistent stream is still
FIFO-consistent.  MEASURED: all 241 push/pop pairs are matched inside a single
block (0 cross-block), so the rewrite never has to reason about control flow.

Blocks are laid independently -- `railflow._lay_once` resets the cursor at every
block -- so per-block coordinate descent over the assignment is an exact search
over that block's row count, not a global heuristic.
"""

import copy

import boustro

BASE_GLYPH = {'ri': 'r', 'sp': 's', 'rp': 'r', 'sc': 's', 'rr': 'r',
              'sd': 's', 'sa': 's', 'ss': 's', 'cc': 's', 'cr': 'r'}


def echo_names(k):
    """Port-name pairs for k echo copies; copy 0 keeps the original names."""
    return [('sp', 'rp')] + [(f'sp{i}', f'rp{i}') for i in range(1, k)]


def glyphs_for(k):
    g = dict(BASE_GLYPH)
    for s, r in echo_names(k)[1:]:
        g[s], g[r] = 's', 'r'
    return g


def bands_for(cols, glyphs):
    b = {}
    b.update(boustro.voronoi_bands(
        [(n, c) for n, c in cols.items() if glyphs[n] == 's']))
    b.update(boustro.voronoi_bands(
        [(n, c) for n, c in cols.items() if glyphs[n] == 'r']))
    return b


def pairs_of(tokens):
    """FIFO-match `sp` pushes to `rp` pops inside one block's token list."""
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
    """Rows this block occupies under boustro.Cursor + railflow terminators."""
    x, d = opmin - 1, 1
    rows = 1
    row0 = True
    for tok in tokens:
        if isinstance(tok, tuple):
            if tok[0] == 'go':
                if d == 1:
                    rows += 1
            elif tok[0] == 'br':
                if row0:
                    rows += 1
                rows += 1        # the private westbound rail row
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
            x = x + (1 if d == -1 else -1)
        else:
            return None
        x = nx
    return rows


def assign_block(tokens, bands, opmin, opmax, k):
    pairs, _loose = pairs_of(tokens)
    if not pairs or k == 1:
        return tokens, sim_rows(tokens, bands, opmin, opmax)
    names = echo_names(k)
    choice = [0] * len(pairs)

    def render(ch):
        out = list(tokens)
        for (pi, po), c in zip(pairs, ch):
            out[pi], out[po] = names[c]
        return out

    best = sim_rows(render(choice), bands, opmin, opmax) or 10 ** 6
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


def rewrite_flow(flow, cols, k, opmin=None):
    """Return (new_flow, glyphs, estimated_total_rows)."""
    glyphs = glyphs_for(k)
    bands = bands_for(cols, glyphs)
    if opmin is None:
        opmin = min(cols.values()) - 3
    opmax = max(cols.values())
    new = copy.deepcopy(flow)
    total = 0
    for label, tokens in flow.blocks.items():
        toks, rows = assign_block(list(tokens), bands, opmin, opmax, k)
        new.blocks[label] = toks
        total += rows or 0
    return new, glyphs, total
