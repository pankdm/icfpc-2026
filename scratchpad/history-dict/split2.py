"""Range-test variant, costed with P1's real group A (2 rows, positions 1..16,
completely unchanged) + group B (extra direct phrases, then the pairs)."""
import sys
sys.path[:0] = ["solutions/history-lesson", "tools"]
import build_ring as base
from littleman import Program

def rows_for(w, cap):
    w = sorted(w, reverse=True)
    for R in range(1, 25):
        nB = -(-len(w) // R)
        TB = [max(w[j*R:(j+1)*R]) for j in range(nB)]
        if sum(TB) + 3*nB <= cap: return R, nB, TB
    return 99, 0, []

SF = list(base.SMALL_FREE)
for RUNS in ([(60, 65)], [(19, 22)], [(19, 22), (60, 65)]):
    slots = SF + [v for a, b in RUNS for v in range(a, b + 1)]
    base.SMALL_FREE = slots
    stream, phrases = base.choose_phrases(base.tokenize(base.TEXT))
    base.SMALL_FREE = SF
    singles = [i for i,(p,s) in enumerate(phrases) if s is True]
    pairs   = [i for i,(p,s) in enumerate(phrases) if s is False]
    pos, n = {}, 0
    for i in singles: pos[i] = slots[n]; n += 1
    nxt = 17
    for i in pairs:
        while nxt == 17: nxt += 1
        pos[i] = nxt; nxt += 1
    syms = []
    for t in stream:
        if t >= 0: syms.append(t)
        elif phrases[-t-1][1] is True: syms.append(pos[-t-1])
        else: syms.extend([base.ESC, pos[-t-1]])
    # group A: positions 1..16, exactly as today (9 phrases + 7 byte entries)
    lowsing = [i for i in singles if pos[i] <= 16]
    wA = [len(str(base.pack128(base.phrase_bytes(phrases[i][0])))) for i in lowsing]
    wA += [len(str(base.pack128(base.spell(v)))) for v in range(1, 17)
           if v not in slots]
    # group B: the extra direct phrases (positions 17+) then the pairs
    hisign = [i for i in singles if pos[i] > 16]
    wB = [len(str(base.pack128(base.phrase_bytes(phrases[i][0]))))
          for i in hisign + pairs] + [1]
    W = 80
    bands = base.optimize_feeder(syms, W)
    p = Program(); f = base.variable_feeder(p, bands, W)
    cap = (W - 4) - 3
    ra, _, _ = rows_for(wA, cap)
    rb, nB, TB = rows_for(wB, cap)
    h = f + 2 + 8 + ra + rb + 2
    print(f"runs={RUNS} direct={len(singles)} esc={len(pairs)} syms={len(syms)}")
    print(f"   W=80 feeder={f} groupA={ra}r groupB={rb}r x{nB}s TB={TB} "
          f"-> height {h}, box {max(W,h)**2}   slack {80-h} rows")
