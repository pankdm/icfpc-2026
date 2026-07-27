#!/usr/bin/env python3
"""Joint phrase selection for history-lesson: a phrase pays only if the feeder
cells it saves exceed the preload cells it costs.

cells per stream symbol = 1/0.4286 = 2.333 (an 18-digit slot holds 9 symbols in
21 cells).  A phrase preloaded as a base-128 packed literal costs
len(str(value)) + 3 cells.  Greedy add/drop on that margin, with a shortest-path
parse recomputed every round.
"""
import collections, math, sys

sys.path.insert(0, "/Users/visenbaev/icfpc26/scratchpad/hist")
import geom2

TXT = "/Users/visenbaev/icfpc26/solutions/history-lesson/icfp-history.txt"
DATA = open(TXT, "rb").read()
YEARS = [b"; %d: " % y for y in range(1997, 2027)]
CELLS_PER_SYM = 21 / 9.0


def split_years(data):
    out, i, hits = bytearray(), 0, 0
    while i < len(data):
        for p in YEARS:
            if data.startswith(p, i):
                out.append(0); i += len(p); hits += 1
                break
        else:
            out.append(data[i]); i += 1
    return bytes(out), hits


BODY, NYEAR = split_years(DATA)
USED = sorted(set(BODY))


def preload_cells(s):
    v = 0
    for i, ch in enumerate(s):
        v |= (ch & 0x7F) << (7 * i)
    return len(str(v)) + 3


def parse(body, costs):
    """shortest path; returns (total symbols, use counter)."""
    n = len(body)
    INF = float("inf")
    best = [INF] * (n + 1); prev = [None] * (n + 1)
    best[0] = 0
    by_first = collections.defaultdict(list)
    for s, c in costs.items():
        by_first[s[0]].append((s, c))
    for i in range(n):
        if best[i] == INF:
            continue
        bi = best[i]
        for s, c in by_first[body[i]]:
            j = i + len(s)
            if j <= n and body[i:j] == s and bi + c < best[j]:
                best[j] = bi + c; prev[j] = s
    use = collections.Counter()
    j = n
    while j:
        s = prev[j]; use[s] += 1; j -= len(s)
    return best[n], use


def run(base, maxphrase=9, rounds=14, cand_min=2, verbose=False):
    cnt = collections.Counter()
    for L in range(2, maxphrase + 1):
        for i in range(len(BODY) - L + 1):
            s = BODY[i:i + L]
            if 0 in s:
                continue
            cnt[s] += 1
    cands = [s for s, c in cnt.items() if c >= cand_min]
    cands.sort(key=lambda s: -cnt[s] * (len(s) - 1))
    cands = cands[:6000]

    ndirect = base - 1                      # one symbol reserved as escape
    chosen = []                             # phrases (singles are always in)

    def costs_for(chosen):
        toks = [bytes([b]) for b in USED] + list(chosen)
        # rank by a cheap proxy first, then by measured use
        c0 = {t: 1 for t in toks}
        _, use = parse(BODY, c0)
        ranked = sorted(toks, key=lambda t: -use[t])
        costs = {}
        for i, t in enumerate(ranked):
            costs[t] = 1 if i < ndirect else 2
        for b in USED:                       # every byte stays encodable
            costs.setdefault(bytes([b]), 2)
        return costs

    cur_costs = costs_for(chosen)
    cur_syms, _ = parse(BODY, cur_costs)
    cur_pre = 0
    cur_total = cur_syms * CELLS_PER_SYM + cur_pre

    for rnd in range(rounds):
        gains = []
        for s in cands:
            if s in chosen:
                continue
            gains.append((cnt[s] * (len(s) - 1) * CELLS_PER_SYM - preload_cells(s), s))
        gains.sort(reverse=True)
        added = 0
        for g, s in gains[:60]:
            if g <= 0:
                break
            trial = chosen + [s]
            tc = costs_for(trial)
            ts, _ = parse(BODY, tc)
            tp = sum(preload_cells(x) for x in trial)
            tt = ts * CELLS_PER_SYM + tp
            if tt < cur_total - 0.001:
                chosen, cur_costs, cur_syms, cur_pre, cur_total = \
                    trial, tc, ts, tp, tt
                added += 1
        if verbose:
            print(f"   round {rnd}: +{added} phrases={len(chosen)} "
                  f"syms={cur_syms} pre={cur_pre} total={cur_total:.0f}")
        if not added:
            break

    # drop pass
    changed = True
    while changed:
        changed = False
        for s in list(chosen):
            trial = [x for x in chosen if x != s]
            tc = costs_for(trial)
            ts, _ = parse(BODY, tc)
            tp = sum(preload_cells(x) for x in trial)
            tt = ts * CELLS_PER_SYM + tp
            if tt < cur_total - 0.001:
                chosen, cur_costs, cur_syms, cur_pre, cur_total = \
                    trial, tc, ts, tp, tt
                changed = True
    return cur_syms, chosen, cur_pre


if __name__ == "__main__":
    print(f"body {len(BODY)} tokens, {len(USED)} distinct, "
          f"{NYEAR} year prefixes folded")
    for base in (92, 100):
        syms, phrases, pre = run(base, verbose=True)
        prerows = math.ceil(pre / 76)
        r = geom2.solve(syms, dec_rows=9 + prerows)[0]
        print(f"base {base}: syms={syms} phrases={len(phrases)} pre={pre} cells "
              f"({prerows} rows) -> box {r[0]} ({r[1]}x{r[2]})")
