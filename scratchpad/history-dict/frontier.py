import sys
sys.path[:0] = ["solutions/history-lesson", "tools"]
import build_ring as base
from littleman import Program

RUNS = [(19, 22), (60, 65)]
SF = list(base.SMALL_FREE)
base.SMALL_FREE = SF + [v for a, b in RUNS for v in range(a, b + 1)]
stream, phrases = base.choose_phrases(base.tokenize(base.TEXT))
singles = [i for i, (p, s) in enumerate(phrases) if s is True]
pairs   = [i for i, (p, s) in enumerate(phrases) if s is False]
slots = base.SMALL_FREE
pos, n = {}, 0
for i in singles: pos[i] = slots[n]; n += 1
nxt = 18
for i in pairs:
    while nxt == 17 or any(a <= nxt <= b for a, b in RUNS): nxt += 1
    pos[i] = nxt; nxt += 1
syms = []
for t in stream:
    if t >= 0: syms.append(t)
    elif phrases[-t-1][1] is True: syms.append(pos[-t-1])
    else: syms.extend([base.ESC, pos[-t-1]])
widths = [len(str(base.pack128(base.phrase_bytes(phrases[i][0]))))
          for i in singles + pairs]
widths += [len(str(base.pack128(base.spell(v))))
           for v in range(1, 17) if v not in slots]
widths = sorted(widths, reverse=True) + [1]
print(f"{len(syms)} symbols, ring {len(widths)} slots")

def p1_rows(w, cap):
    w = sorted(w, reverse=True)
    for R in range(1, 20):
        nB = -(-len(w) // R)
        TB = [max(w[j*R:(j+1)*R]) for j in range(nB)]
        if sum(TB) + 3*nB <= cap: return R
    return 99

for W in (81, 80, 79, 78, 77):
    bands = base.optimize_feeder(syms, W)
    p = Program(); f = base.variable_feeder(p, bands, W)
    cap = (W - 4) - 3          # sum(TB)+3nB <= inner-3
    pr = p1_rows(widths, cap)
    h = f + 2 + 8 + pr + 2
    print(f"W={W}: feeder={f} P1cap={cap} P1={pr}r -> height {h}, "
          f"box {max(W,h)}^2 = {max(W,h)**2}")
