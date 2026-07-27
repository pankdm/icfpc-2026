"""Price a dense byte->symbol map: does it buy feeder rows net of P1?"""
import sys
sys.path[:0] = ["solutions/history-lesson", "tools"]
import build_ring as base
from littleman import Program

CAP = 73

def p1_rows(widths):
    w = sorted(widths, reverse=True)
    for R in range(1, 20):
        nB = -(-len(w) // R)
        TB = [max(w[j*R:(j+1)*R]) for j in range(nB)]
        if sum(TB) + 3*nB <= CAP:
            return R
    return 99

def run(D, stolen, label):
    base.SMALL_FREE = list(range(1, D + 1))
    base.STOLEN = stolen
    stream, phrases = base.choose_phrases(base.tokenize(base.TEXT))
    singles = [i for i, (p, s) in enumerate(phrases) if s is True]
    pairs   = [i for i, (p, s) in enumerate(phrases) if s is False]
    pos = {}
    for n, i in enumerate(singles, start=1):          # direct: 1..D
        pos[i] = n
    ESC = D + 2                                        # D+1 stays reserved
    raw = sorted({t for t in stream if t >= 0})
    dense = {}
    nxt = D + 3
    for t in raw:
        dense[t] = nxt; nxt += 1
    assert nxt - 1 <= 91, f"symbol space overflow: {nxt-1}"
    for n, i in enumerate(pairs, start=len(singles) + 1):
        pos[i] = n
    syms = []
    for t in stream:
        if t >= 0:
            syms.append(dense[t])
        elif -t - 1 in pos and phrases[-t - 1][1] is True:
            syms.append(pos[-t - 1])
        else:
            syms.extend([ESC, pos[-t - 1]])
    widths = sorted((len(str(base.pack128(base.phrase_bytes(phrases[i][0]))))
                     for i in singles + pairs), reverse=True) + [1]
    bands = base.optimize_feeder(syms, 80)
    p = Program(); frows = base.variable_feeder(p, bands, 80)
    pr = p1_rows(widths)
    total = frows + 2 + 8 + (pr + 2)
    print(f"{label:22s} syms={len(syms):5d} distinct-raw={len(raw):3d} "
          f"top-symbol={nxt-1:3d} | feeder={frows} P1-table={pr}r "
          f"| TOTAL {total}")
    return total

print("baseline (today) : 2042 symbols, feeder=64, P1 table 6r, TOTAL 82")
for D in (12, 16, 18):
    run(D, (), f"dense map D={D}")
