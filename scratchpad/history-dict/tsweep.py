import sys; sys.path[:0]=['solutions/history-lesson','tools']
import build_ring as b
from littleman import Program

FREE = b.free_symbols()
for T in (19, 20, 21, 22, 29, 30):
    if T not in FREE: continue
    esc = next(v for v in FREE if v > T)
    best = None
    for rb in (3, 4, 5):
        try:
            with b.alphabet(T, esc):
                syms, ring, l = b.build_encoding(west_first=True, group_b_rows=rb)
            tb = l["TB"]
            if sum(tb) + 3*len(tb) > 73: continue
            smalls = [ring[v] for v in range(1, l["n_small"]+1)]
            _, _, RA, nA = b.group_a_grid(smalls, True, 73)
            if best is None or RA + rb < best[0]:
                best = (RA + rb, RA, rb, syms, tb)
        except Exception as e:
            pass
    if best is None:
        print(f"T={T}: no feasible layout"); continue
    tot, RA, RB, syms, tb = best
    bands = b.optimize_feeder(syms, 80)
    p = Program(); f = b.variable_feeder(p, bands, 80)
    h = f + 2 + 8 + tot + 2
    print(f"T={T:2d} ESC={esc:2d} syms={len(syms)} feeder={f} "
          f"A={RA}r B={RB}r -> height {h}  box {max(80,h)**2}")
