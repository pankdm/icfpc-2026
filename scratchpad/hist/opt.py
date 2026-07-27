#!/usr/bin/env python3
"""Joint optimiser: base B, escape-chain levels, phrase dictionary, geometry.

Objective is the SQUARE BOX, computed exactly:
  * a slot of d digits holds n symbols (B^n <= min(10^d, 2^63)) and costs d+3
    cells; a feeder row of usable width U = S-5 is an unbounded knapsack over d;
  * the token stream is parsed by shortest path, tokens are ranked by use and
    laid into escape-chain levels of B-1 (last level B), cost = level index;
  * phrases are preloaded as base-128 packed literals, len(str(v))+3 cells each,
    and share the feeder rows.
Nothing is printed but numbers.
"""
import collections, math, sys

sys.path.insert(0, "/Users/visenbaev/icfpc26/scratchpad/hist")
from enc2 import BODY, USED, parse

DEC_ROWS = 9                      # 7 decoder rows + 2 walls (measured on 81x81)


def slot_syms(B, d):
    n = 0
    while B ** (n + 1) <= 10 ** d and B ** (n + 1) < 2 ** 63:
        n += 1
    return n


def row_capacity(B, U, memo={}):
    key = (B, U)
    if key in memo:
        return memo[key]
    best = [0] * (U + 1)
    for u in range(1, U + 1):
        for d in range(1, 20):
            c = d + 3
            if c <= u:
                v = best[u - c] + slot_syms(B, d)
                if v > best[u]:
                    best[u] = v
    memo[key] = best[U]
    return best[U]


def chain_levels(ntok, B):
    """level index (1-based) for each rank 0..ntok-1"""
    lv, i, k = [], 0, 1
    while i < ntok:
        cap = B - 1 if i + (B - 1) < ntok else B
        take = min(cap, ntok - i)
        lv += [k] * take
        i += take
        k += 1
    return lv


def stream_cost(chosen, B):
    toks = [bytes([b]) for b in USED] + list(chosen)
    _, use = parse(BODY, {t: 1 for t in toks})
    ranked = sorted(toks, key=lambda t: -use[t])
    lv = chain_levels(len(ranked), B)
    syms = sum(lv[i] * use[t] for i, t in enumerate(ranked))
    return syms, max(lv)


def preload_cells(s):
    v = 0
    for i, ch in enumerate(s):
        v |= (ch & 0x7F) << (7 * i)
    return len(str(v)) + 3


def box_for(syms, pre, B):
    best = None
    for S in range(58, 90):
        U = S - 5
        cap = row_capacity(B, U)
        if cap == 0:
            continue
        cells_per_row_syms = cap
        rows_stream = math.ceil(syms / cells_per_row_syms)
        rows_pre = math.ceil(pre / U)
        H = rows_stream + rows_pre + DEC_ROWS
        b = max(S, H) ** 2
        if best is None or b < best[0]:
            best = (b, S, H, rows_stream, rows_pre, cap)
    return best


def optimise(B, cand_limit=700, verbose=False):
    cnt = collections.Counter()
    for L in range(2, 10):
        for i in range(len(BODY) - L + 1):
            s = BODY[i:i + L]
            if 0 in s:
                continue
            cnt[s] += 1
    cands = [s for s, c in cnt.items() if c >= 2]
    cands.sort(key=lambda s: -cnt[s] * (len(s) - 1))
    cands = cands[:cand_limit]

    chosen = []
    syms, depth = stream_cost(chosen, B)
    pre = 0
    cur = box_for(syms, pre, B)
    for rnd in range(60):
        best = None
        for s in cands:
            if s in chosen:
                continue
            trial = chosen + [s]
            ts, td = stream_cost(trial, B)
            tp = pre + preload_cells(s)
            tb = box_for(ts, tp, B)
            # tie-break on total cells so progress continues inside a box plateau
            key = (tb[0], ts * 1.0 + tp)
            if best is None or key < best[0]:
                best = (key, s, ts, tp, tb)
        if best is None:
            break
        keycur = (cur[0], syms * 1.0 + pre)
        if best[0] >= keycur:
            break
        _, s, syms, pre, cur = best
        chosen.append(s)
        if verbose:
            print(f"    +{s!r} n={len(chosen)} syms={syms} pre={pre} box={cur[0]}")
    return syms, pre, chosen, cur


if __name__ == "__main__":
    print(f"body={len(BODY)} tokens, {len(USED)} distinct")
    print(" B  syms  depth  phrases  pre  ->  box    (S x H)  rows(stream/pre) cap")
    results = []
    for B in (16, 20, 24, 28, 32, 40, 48, 64, 92):
        syms, pre, chosen, bx = optimise(B)
        _, depth = stream_cost(chosen, B)
        results.append((bx[0], B, syms, depth, len(chosen), pre, bx))
        print(f"{B:3d} {syms:5d} {depth:5d} {len(chosen):8d} {pre:5d}  -> "
              f"{bx[0]:5d}  ({bx[1]}x{bx[2]})  {bx[3]}/{bx[4]}  cap={bx[5]}",
              flush=True)
    results.sort()
    print("BEST:", results[0][:6])
