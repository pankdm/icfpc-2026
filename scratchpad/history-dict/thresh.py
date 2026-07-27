"""Raise DISP's threshold T instead of adding range tests.

DISP's classifier is unchanged in SHAPE: A = v - T; A<0 -> ring position v;
A>0 -> ESC test then byte = v+31.  Only two literals change (17 -> T, and the
ESC constant).  Every free symbol below T becomes a direct dictionary slot;
every used symbol below T needs a cheap packed-byte ring entry.
"""
import sys
sys.path[:0] = ["solutions/history-lesson", "tools"]
import build_ring as base
from littleman import Program

toks = set(t for t in base.tokenize(base.TEXT) if t > 0)
FREE = [v for v in range(1, 92) if v not in toks]
print("free symbols:", FREE)

def p1_rows(w, cap):
    w = sorted(w, reverse=True)
    for R in range(1, 25):
        nB = -(-len(w) // R)
        TB = [max(w[j*R:(j+1)*R]) for j in range(nB)]
        if sum(TB) + 3*nB <= cap: return R
    return 99

SF, ST, E0 = list(base.SMALL_FREE), tuple(base.STOLEN), base.ESC
for T in (17, 22, 30, 31, 33):
    esc = next(v for v in FREE if v > T)
    slots = [v for v in FREE if v < T] + [8]          # 8 stolen as today
    slots = sorted(set(slots))
    bytes_below = [v for v in range(1, T) if v not in slots]
    base.SMALL_FREE, base.STOLEN, base.ESC = slots, (8,), esc
    stream, phrases = base.choose_phrases(base.tokenize(base.TEXT))
    singles = [i for i,(p,s) in enumerate(phrases) if s is True]
    pairs   = [i for i,(p,s) in enumerate(phrases) if s is False]
    pos, n = {}, 0
    for i in singles: pos[i] = slots[n]; n += 1
    nxt = T
    for i in pairs: pos[i] = nxt; nxt += 1
    syms = []
    for t in stream:
        if t >= 0: syms.append(t)
        elif phrases[-t-1][1] is True: syms.append(pos[-t-1])
        else: syms.extend([esc, pos[-t-1]])
    assert nxt - 1 <= 91, nxt
    ph_w = [len(str(base.pack128(base.phrase_bytes(phrases[i][0]))))
            for i in singles + pairs]
    by_w = [len(str(base.pack128(base.spell(v)))) for v in bytes_below]
    widths = sorted(ph_w + by_w, reverse=True) + [1]
    for W in (81, 80):
        bands = base.optimize_feeder(syms, W)
        p = Program(); f = base.variable_feeder(p, bands, W)
        pr = p1_rows(widths, (W - 4) - 3)
        h = f + 2 + 8 + pr + 2
        print(f"T={T:2d} ESC={esc:2d} direct={len(singles)} esc={len(pairs)} "
              f"bytes={len(by_w)} ring={len(widths)} syms={len(syms)} | "
              f"W={W} feeder={f} P1={pr}r height={h} box={max(W,h)**2}")
base.SMALL_FREE, base.STOLEN, base.ESC = SF, ST, E0
