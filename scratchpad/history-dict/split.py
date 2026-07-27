"""Same sweep, but P1 is costed as it is really built: group A (the direct
positions, which must preload FIRST) then group B (the escaped pairs)."""
import sys
sys.path[:0] = ["solutions/history-lesson", "tools"]
import build_ring as base
from littleman import Program

toks = set(t for t in base.tokenize(base.TEXT) if t > 0)
FREE = [v for v in range(1, 92) if v not in toks]

def rows_for(w, cap):
    w = sorted(w, reverse=True)
    for R in range(1, 25):
        nB = -(-len(w) // R)
        TB = [max(w[j*R:(j+1)*R]) for j in range(nB)]
        if sum(TB) + 3*nB <= cap: return R
    return 99

def evaluate(label, slots, esc, extra_runs, Ws=(81, 80)):
    """slots: symbol values usable as direct dictionary refs (ordered)."""
    SF, ST, E0 = list(base.SMALL_FREE), tuple(base.STOLEN), base.ESC
    base.SMALL_FREE, base.STOLEN, base.ESC = slots, (8,), esc
    stream, phrases = base.choose_phrases(base.tokenize(base.TEXT))
    singles = [i for i,(p,s) in enumerate(phrases) if s is True]
    pairs   = [i for i,(p,s) in enumerate(phrases) if s is False]
    pos, n = {}, 0
    for i in singles: pos[i] = slots[n]; n += 1
    # every symbol that DISP routes to the ring occupies a group-A position
    direct = sorted(set(slots) | {v for a,b in extra_runs for v in range(a,b+1)})
    ndirect = max(direct) if not extra_runs else len(direct) + len(
        [v for v in range(1, min(min(direct), 99)) if False])
    base.SMALL_FREE, base.STOLEN, base.ESC = SF, ST, E0
    return stream, phrases, singles, pairs, pos

# ---- variant 1: raise the threshold T (one literal changes in DISP)
for T in (30, 31, 33):
    esc = next(v for v in FREE if v > T)
    slots = sorted(set([v for v in FREE if v < T] + [8]))
    bytes_below = [v for v in range(1, T) if v not in slots]
    SF, ST, E0 = list(base.SMALL_FREE), tuple(base.STOLEN), base.ESC
    base.SMALL_FREE, base.STOLEN, base.ESC = slots, (8,), esc
    stream, phrases = base.choose_phrases(base.tokenize(base.TEXT))
    base.SMALL_FREE, base.STOLEN, base.ESC = SF, ST, E0
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
    # group A = the T-1 direct positions; group B = the pairs + sentinel
    wA = [len(str(base.pack128(base.phrase_bytes(phrases[i][0])))) for i in singles]
    wA += [len(str(base.pack128(base.spell(v)))) for v in bytes_below]
    wB = [len(str(base.pack128(base.phrase_bytes(phrases[i][0])))) for i in pairs] + [1]
    for W in (80,):
        bands = base.optimize_feeder(syms, W)
        p = Program(); f = base.variable_feeder(p, bands, W)
        cap = (W - 4) - 3
        ra, rb = rows_for(wA, cap), rows_for(wB, cap)
        h = f + 2 + 8 + ra + rb + 2
        print(f"T={T:2d} ESC={esc:2d} direct={len(singles)} bytes={len(bytes_below)} "
              f"syms={len(syms)} | W={W} feeder={f} A={ra}r B={rb}r "
              f"height={h} box={max(W,h)**2}")
