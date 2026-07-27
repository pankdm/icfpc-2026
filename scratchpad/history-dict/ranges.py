"""Realistic variant: byte = v+31 unchanged; extra direct dictionary slots
taken from the free symbol runs, each costing DISP one range test."""
import sys
sys.path[:0] = ["solutions/history-lesson", "tools"]
import build_ring as base
from littleman import Program

CAP = 73
EXTRA_RUNS = {0: [], 4: [(19, 22)], 10: [(19, 22), (60, 65)],
              14: [(19, 22), (60, 65), (4, 7)]}

def p1_rows(widths):
    w = sorted(widths, reverse=True)
    for R in range(1, 20):
        nB = -(-len(w) // R)
        TB = [max(w[j*R:(j+1)*R]) for j in range(nB)]
        if sum(TB) + 3*nB <= CAP:
            return R
    return 99

SF = list(base.SMALL_FREE)
for extra, runs in EXTRA_RUNS.items():
    slots = SF + [v for a, b in runs for v in range(a, b + 1)]
    base.SMALL_FREE = slots
    stream, phrases = base.choose_phrases(base.tokenize(base.TEXT))
    singles = [i for i, (p, s) in enumerate(phrases) if s is True]
    pairs   = [i for i, (p, s) in enumerate(phrases) if s is False]
    # ring: positions 1..16 as today (phrases at free slots, bytes elsewhere),
    # then the extra runs, then the escaped pairs.
    pos, n = {}, 0
    for i in singles:
        pos[i] = slots[n]; n += 1
    ESC = base.ESC
    nxt = 17
    for i in pairs:
        while nxt in (17,) or any(a <= nxt <= b for a, b in runs):
            nxt += 1
        pos[i] = nxt; nxt += 1
    syms = []
    for t in stream:
        if t >= 0:
            syms.append(t)
        elif phrases[-t - 1][1] is True:
            syms.append(pos[-t - 1])
        else:
            syms.extend([ESC, pos[-t - 1]])
    widths = [len(str(base.pack128(base.phrase_bytes(phrases[i][0]))))
              for i in singles + pairs]
    widths += [len(str(base.pack128(base.spell(v))))
               for v in range(1, 17) if v not in slots]      # byte entries
    widths = sorted(widths, reverse=True) + [1]
    bands = base.optimize_feeder(syms, 80)
    p = Program(); frows = base.variable_feeder(p, bands, 80)
    pr = p1_rows(widths)
    total = frows + 2 + 8 + pr + 2
    print(f"extra={extra:2d} runs={runs}  direct={len(singles)} esc={len(pairs)} "
          f"| syms={len(syms)} feeder={frows} ring={len(widths)} P1={pr}r "
          f"| TOTAL {total}  score {max(80,total)**2}")
base.SMALL_FREE = SF
