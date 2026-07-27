"""For each dictionary size, find the fewest P1 group-B rows that fit W=80."""
import sys
sys.path[:0] = ["solutions/history-lesson", "tools"]
import build_ring as base

INNER = 76                       # width 80 - 4
FEEDER = {0: 64, 3: 63, 6: 62, 10: 61, 14: 61}   # measured content rows at W=80

def best_rows(widths):
    """widths: digit counts of every group-B slot (entries + sentinel).
    The builder sorts descending and chunks into groups of R; TB[j] is the
    group max.  Returns the smallest feasible R."""
    w = sorted(widths, reverse=True)
    for R in range(1, 12):
        nB = -(-len(w) // R)
        TB = [max(w[j * R:(j + 1) * R] or [1]) for j in range(nB)]
        if sum(TB) + 3 * nB + 4 <= INNER + 1:
            return R, nB, TB
    return None

print(f"{'extra':>5} {'entries':>7} {'feeder':>6} {'R':>2} {'nB':>2} "
      f"{'P1 room':>7} {'TOTAL':>6}  TB")
for extra, frows in FEEDER.items():
    syms, ring, layout = base.build_encoding(
        extra_pair_count=extra, tail_constants=False, west_first=True)
    # group-B slots = every ring entry above the 16 smalls, plus the sentinel
    vals = [ring[p] for p in sorted(ring) if p > 16]
    widths = [len(str(v)) for v in vals] + [1]      # +1 zero sentinel
    got = best_rows(widths)
    if not got:
        print(f"{extra:5d} {len(ring):7d} {frows:6d}   infeasible")
        continue
    R, nB, TB = got
    total = (frows + 2) + 8 + (R + 4)
    print(f"{extra:5d} {len(ring):7d} {frows:6d} {R:2d} {nB:2d} {R+4:7d} "
          f"{total:6d}  {TB}")
