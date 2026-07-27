#!/usr/bin/env python3
"""What cell counts make brackets' 16x16 reachable? Pre-computed, so the box step
can ship the moment the tick work shrinks a room.

Today: M 56 cells in 11x11, P 20 in 6x8, C 28 in 12x6, I/O 3x3, box 17x17=289.
The live packing is M top-left, P east of M, C south spanning to the right edge,
so width = M_w + P_w and height = M_h + C_h.

For every (M_cells, C_cells) this finds the smallest box each room-rectangle
choice reaches and the worst interior fill that choice demands, so the answer to
"how many cells must the tick redesign save?" is a lookup, not a re-derivation.

  python3 brk3_need.py [box] [max_fill]
"""
import sys

BOX = int(sys.argv[1]) if len(sys.argv) > 1 else 16
MAXFILL = float(sys.argv[2]) if len(sys.argv) > 2 else 0.85
P_NEED = 20


def rects(need, maxfill):
    """(w, h, fill) rectangles whose interior can hold `need` cells.

    A 1- or 2-cell-wide interior cannot carry a branching walk, so both interior
    dimensions must be >= 3.
    """
    out = []
    for w in range(5, BOX - 3):
        for h in range(5, BOX + 1):
            iw, ih = w - 2, h - 2
            if min(iw, ih) < 3:
                continue
            inter = iw * ih
            if need > inter * maxfill:
                continue
            out.append((w, h, need / inter))
    return out


def best_for(m_need, c_need, maxfill):
    """Smallest achievable box under width = M_w+P_w, height = M_h+C_h."""
    best = None
    for mw, mh, mf in rects(m_need, maxfill):
        for pw, ph, pf in rects(P_NEED, maxfill):
            if ph > mh:                      # P sits beside M, within its height
                continue
            for cw, ch, cf in rects(c_need, maxfill):
                if cw > mw + pw:
                    continue
                side = max(mw + pw, mh + ch)
                if side > BOX:
                    continue
                cand = (side, round(max(mf, pf, cf), 3),
                        f"M {mw}x{mh} P {pw}x{ph} C {cw}x{ch}")
                if best is None or cand[:2] < best[:2]:
                    best = cand
    return best


print(f"target box {BOX}x{BOX}, max interior fill {MAXFILL:.0%}")
print("  M    C   -> best side  worst fill  shapes")
hit = []
for m in range(56, 35, -2):
    for c in range(28, 17, -2):
        b = best_for(m, c, MAXFILL)
        if not b:
            continue
        mark = "  <== reaches target" if b[0] <= BOX else ""
        if b[0] <= BOX:
            hit.append((m, c, b))
        print(f"  {m:2d}  {c:2d}   -> {b[0]:2d}         {b[1]:.0%}       {b[2]}{mark}")
if hit:
    m, c, b = max(hit, key=lambda t: (t[0], t[1]))
    print(f"\nCHEAPEST QUALIFYING REDUCTION: M {m} cells (save {56 - m}), "
          f"C {c} cells (save {28 - c})  ->  {b[2]}")
else:
    print(f"\nno (M, C) in range reaches {BOX}x{BOX} at {MAXFILL:.0%} fill")
