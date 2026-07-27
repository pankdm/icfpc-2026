#!/usr/bin/env python3
"""Base sweep with a CORRECT escape chain.

One symbol of the alphabet is the escape.  A token is reached in k symbols:
level 1 holds B-1 tokens, each further level holds B-1 more (its own escape
chains on), and the deepest level may use all B.  Cost = sum f_i * len_i, and
feeder cells = cost * cells_per_symbol(B).

Also prints the B-ary Huffman bound, which is what a general (table-driven)
decoder could reach -- the gap between the two is what an escape chain gives up.
"""
import collections, heapq, math, sys

sys.path.insert(0, "/Users/visenbaev/icfpc26/scratchpad/hist")
from enc2 import BODY, USED, parse


def cells_per_symbol(B):
    best = None
    for d in range(4, 20):
        n = 0
        while B ** (n + 1) <= 10 ** d and B ** (n + 1) < 2 ** 63:
            n += 1
        if n and (best is None or (d + 3) / n < best[0]):
            best = ((d + 3) / n, d, n)
    return best


def chain_cost(freqs, B):
    """freqs sorted desc; escape chain of levels of size B-1 (last may be B)."""
    tot, i, lvl = 0, 0, 1
    n = len(freqs)
    while i < n:
        cap = B - 1 if i + (B - 1) < n else B
        take = min(cap, n - i)
        tot += lvl * sum(freqs[i:i + take])
        i += take
        lvl += 1
    return tot


def huffman_cost(freqs, B):
    """B-ary Huffman: pad so (n-1) % (B-1) == 0."""
    f = list(freqs)
    if B < 2:
        return None
    while (len(f) - 1) % (B - 1) != 0:
        f.append(0)
    h = [(x, 0) for x in f]
    heapq.heapify(h)
    tot = 0
    while len(h) > 1:
        s = 0
        for _ in range(B):
            if h:
                s += heapq.heappop(h)[0]
        tot += s
        heapq.heappush(h, (s, 0))
    return tot


def main(chosen=()):
    toks = [bytes([b]) for b in USED] + list(chosen)
    _, use = parse(BODY, {t: 1 for t in toks})
    freqs = sorted((use[t] for t in toks), reverse=True)
    total_uses = sum(freqs)
    print(f"tokens={len(toks)} uses={total_uses}")
    print("  B   d  n  cells/sym   chain-syms  chain-cells | huff-syms huff-cells")
    rows = []
    for B in (8, 12, 16, 20, 24, 28, 32, 40, 48, 56, 64, 80, 92, 100, 128):
        cps, d, n = cells_per_symbol(B)
        cs = chain_cost(freqs, B)
        hs = huffman_cost(freqs, B)
        rows.append((cs * cps, B, cs, hs * cps))
        print(f"{B:4d} {d:3d} {n:2d}   {cps:.3f}      {cs:6d}    {cs*cps:8.0f} | "
              f"{hs:7d}  {hs*cps:8.0f}")
    rows.sort()
    print(f"best chain: B={rows[0][1]} cells={rows[0][0]:.0f}")
    return rows[0]


if __name__ == "__main__":
    main()
