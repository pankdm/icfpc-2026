#!/usr/bin/env python3
"""Best encoding reachable WITHOUT touching the decoder.

build_ring.py's alphabet is fixed: symbol 0 = year marker, 1..16 = direct ring
slots, 29 = escape (`29,k` -> ring slot k), every other symbol 17..91 = raw
ASCII at symbol+31 (so ASCII 48..122 is free, no ring slot).  Bytes below 48
(space and punctuation) therefore MUST occupy ring slots, competing with
phrases for the 16 direct positions.

What is optimised here and not in build_ring.py:
  * the parse is a shortest path, not greedy;
  * which tokens get the 16 direct slots is chosen by measured use, not by a
    fixed "punctuation first" rule;
  * the phrase set is grown on the exact marginal box, not on a proxy.
"""
import collections, math, sys

sys.path.insert(0, "/Users/visenbaev/icfpc26/scratchpad/hist")
from enc2 import BODY, USED, parse
import opt as O

DIRECT_SLOTS = 16
ESC_SLOTS = 19                 # ring positions 17..35 reachable via `29,k`
B = 92


def preload_cells(s):
    v = 0
    for i, ch in enumerate(s):
        v |= (ch & 0x7F) << (7 * i)
    return len(str(v)) + 3


FREE = {bytes([b]) for b in USED if 48 <= b <= 122}      # raw, cost 1, no ring
NEEDS_RING = [bytes([b]) for b in USED if not (48 <= b <= 122) and b != 0]


def evaluate(phrases):
    """assign ring slots by measured use; return (syms, preload_cells) or None"""
    ring_tokens = NEEDS_RING + list(phrases)
    if len(ring_tokens) > DIRECT_SLOTS + ESC_SLOTS:
        return None
    toks = list(FREE) + ring_tokens + [b"\x00"]
    _, use = parse(BODY, {t: 1 for t in toks})
    ranked = sorted(ring_tokens, key=lambda t: -use[t])
    cost = {t: 1 for t in FREE}
    cost[b"\x00"] = 1
    for i, t in enumerate(ranked):
        cost[t] = 1 if i < DIRECT_SLOTS else 2
    syms, _ = parse(BODY, cost)
    pre = sum(preload_cells(t) for t in ring_tokens)
    return syms, pre


def main():
    cnt = collections.Counter()
    for L in range(2, 10):
        for i in range(len(BODY) - L + 1):
            s = BODY[i:i + L]
            if 0 in s:
                continue
            cnt[s] += 1
    cands = [s for s, c in cnt.items() if c >= 2]
    cands.sort(key=lambda s: -cnt[s] * (len(s) - 1))
    cands = cands[:800]

    chosen = []
    syms, pre = evaluate(chosen)
    cur = O.box_for(syms, pre, B)
    print(f"start: syms={syms} pre={pre} box={cur[0]} ({cur[1]}x{cur[2]})")
    for rnd in range(ESC_SLOTS + DIRECT_SLOTS):
        best = None
        for s in cands:
            if s in chosen:
                continue
            r = evaluate(chosen + [s])
            if r is None:
                continue
            ts, tp = r
            tb = O.box_for(ts, tp, B)
            key = (tb[0], ts + tp)
            if best is None or key < best[0]:
                best = (key, s, ts, tp, tb)
        if best is None or best[0] >= (cur[0], syms + pre):
            break
        _, s, syms, pre, cur = best
        chosen.append(s)
        print(f"  +{len(chosen):2d} syms={syms} pre={pre} box={cur[0]} "
              f"({cur[1]}x{cur[2]}) rows {cur[3]}/{cur[4]}", flush=True)
    print(f"FINAL compat: syms={syms} phrases={len(chosen)} pre={pre} "
          f"box={cur[0]} ({cur[1]}x{cur[2]})")


if __name__ == "__main__":
    main()
