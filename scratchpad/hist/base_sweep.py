#!/usr/bin/env python3
"""Which base minimises FEEDER CELLS, not symbols?

A slot of d digits holds n symbols where B^n <= min(10^d, 2^63); cells = d+3.
A small base packs more symbols per slot (cheaper per symbol) but needs more
escape pairs; a large base is the opposite.  Sweep B against a fixed token
stream and report cells.
"""
import collections, math, sys

sys.path.insert(0, "/Users/visenbaev/icfpc26/scratchpad/hist")
from enc2 import BODY, USED, parse, preload_cells


def cells_per_symbol(B):
    best = None
    for d in range(4, 20):
        n = 0
        while B ** (n + 1) <= 10 ** d and B ** (n + 1) < 2 ** 63:
            n += 1
        if n:
            c = (d + 3) / n
            if best is None or c < best[0]:
                best = (c, d, n)
    return best


def stream_uses(chosen):
    toks = [bytes([b]) for b in USED] + list(chosen)
    _, use = parse(BODY, {t: 1 for t in toks})
    return use, toks


def cost_for_base(B, use, toks):
    ranked = sorted(toks, key=lambda t: -use[t])
    nd = B - 1
    syms = sum(use[t] for t in ranked[:nd]) + 2 * sum(use[t] for t in ranked[nd:])
    cps, d, n = cells_per_symbol(B)
    return syms, syms * cps, cps, d, n


if __name__ == "__main__":
    import json
    chosen = [bytes(x) for x in json.load(open(sys.argv[1]))] if len(sys.argv) > 1 else []
    use, toks = stream_uses(chosen)
    print(f"tokens={len(toks)} (singles {len(USED)} + phrases {len(chosen)})")
    print(" B   d   n  cells/sym   syms   feeder cells")
    rows = []
    for B in (16, 24, 32, 40, 48, 60, 64, 72, 80, 90, 92, 96, 100, 110, 120, 128, 160, 200):
        syms, cells, cps, d, n = cost_for_base(B, use, toks)
        rows.append((cells, B, d, n, cps, syms))
        print(f"{B:4d} {d:3d} {n:3d}   {cps:.3f}   {syms:5d}   {cells:8.0f}")
    rows.sort()
    print("best:", rows[0])
