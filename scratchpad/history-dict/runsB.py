"""Route B candidates: which recycled runs reach height<=80, and what does
each cost DISP (position offset -> that many `m` on BP, which is free)."""
import sys; sys.path[:0]=['solutions/history-lesson','tools']
import build_ring as b
from littleman import Program

def rows_for(w, cap):
    w = sorted(w, reverse=True)
    for R in range(1, 25):
        nB = -(-len(w) // R)
        TB = [max(w[j*R:(j+1)*R]) for j in range(nB)]
        if sum(TB) + 3*nB <= cap: return R
    return 99

SF = list(b.SMALL_FREE)
CASES = [
    ([(19, 22), (60, 65)], 29),
    ([(19, 22), (29, 31)], 33),
    ([(19, 22), (29, 31), (33, 33)], 58),
    ([(19, 22), (29, 31), (60, 65)], 33),
]
for RUNS, esc in CASES:
    slots = sorted(SF + [v for a, c in RUNS for v in range(a, c + 1)])
    old_esc = b.ESC
    b.SMALL_FREE, b.ESC = slots, esc
    stream, phrases = b.choose_phrases(b.tokenize(b.TEXT))
    b.SMALL_FREE, b.ESC = SF, old_esc
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
        else: syms.extend([esc, pos[-t-1]])
    low = [i for i in singles if pos[i] <= 16]
    wA = [len(str(b.pack128(b.phrase_bytes(phrases[i][0])))) for i in low]
    wA += [len(str(b.pack128(b.spell(v)))) for v in range(1,17) if v not in slots]
    hi = [i for i in singles if pos[i] > 16]
    wB = [len(str(b.pack128(b.phrase_bytes(phrases[i][0])))) for i in hi+pairs]+[1]
    bands = b.optimize_feeder(syms, 80)
    p = Program(); f = b.variable_feeder(p, bands, 80)
    ra, rb = rows_for(wA, 73), rows_for(wB, 73)
    h = f + 2 + 8 + ra + rb + 2
    ring = 16 + len(hi) + len(pairs)
    # position offsets: run starting at symbol a lands at position 17+k
    offs, k = [], 17
    for a, c in RUNS:
        offs.append(a - k); k += c - a + 1
    print(f"runs={RUNS} ESC={esc} direct={len(singles)} syms={len(syms)} "
          f"feeder={f} A={ra}r B={rb}r -> height {h} box {max(80,h)**2} "
          f"| ring={ring}w offsets={offs}")
