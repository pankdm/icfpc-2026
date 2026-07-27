#!/usr/bin/env python3
"""Geometric model of the history-lesson ring build.

Answers: how many cells/symbol does the current feeder achieve, what is the
knapsack optimum at that width, and what box does each (machine rows, symbols,
cells-per-symbol) triple reach.  Prints numbers only.
"""
import math
import os
import sys

HL = "/Users/visenbaev/icfpc26/solutions/history-lesson"
sys.path.insert(0, HL)
os.chdir(HL)

I64 = 2 ** 63 - 1


def slot_syms(B, d):
    """symbols a d-digit decimal slot can hold in base B (i64 both ways)."""
    n = 0
    while B ** (n + 1) <= 10 ** d and B ** (n + 1) - 1 <= I64:
        n += 1
    return n


def knap(B, U):
    """best symbols in a feeder row of usable width U (slot costs d+3)."""
    best = [0] * (U + 1)
    pick = [None] * (U + 1)
    for u in range(1, U + 1):
        best[u] = best[u - 1]
        pick[u] = pick[u - 1]
        for d in range(1, 19):
            c = d + 3
            if c <= u and best[u - c] + slot_syms(B, d) > best[u]:
                best[u] = best[u - c] + slot_syms(B, d)
                pick[u] = d
    return best[U]


def box_for(nsym, cps, mach_rows, fixed=5):
    """smallest square S with (S-fixed)/cps * (S-mach_rows) >= nsym."""
    for S in range(40, 140):
        rows = S - mach_rows
        if rows <= 0:
            continue
        per = (S - fixed) / cps
        if per * rows >= nsym:
            return S
    return None


def main():
    import build_ring as BR
    # measure the champion's feeder
    man = os.path.join(HL, "best", "81x81.man")
    L = [l.rstrip("\n") for l in open(man)]
    W = max(len(l.rstrip()) for l in L)
    H = max(i + 1 for i, l in enumerate(L) if l.strip())
    feeder = L[1:64]
    dig = sum(sum(ch.isdigit() for ch in r) for r in feeder)
    bt = sum(r.count("`") for r in feeder)
    print("champion %dx%d box %d" % (W, H, max(W, H) ** 2))
    print("  feeder rows %d  digits %d  backticks %d  slots %d"
          % (len(feeder), dig, bt, bt // 2))
    cells = dig + bt + bt // 2            # digits + ticks + one send per slot
    print("  feeder payload cells %d" % cells)

    for B in (92,):
        print("  knapsack optimum at U=%d base %d: %d syms/row"
              % (W - 5, B, knap(B, W - 5)))
    # symbols actually carried
    try:
        syms = BR.build_stream()[0] if hasattr(BR, "build_stream") else None
    except Exception:
        syms = None
    print("  (symbols per row achieved) = payload/rows ->", round(cells / len(feeder), 2),
          "cells/row")

    for nsym in (2042,):
        opt = knap(92, W - 5)
        print("  cells/sym achieved = %.3f   knapsack ideal = %.3f"
              % (cells / nsym, (W - 5) / opt))
    print()
    print("  box reachable, by (machine rows, cells/sym, symbols):")
    for mach in (18, 16, 14, 12, 10, 8):
        row = []
        for cps in (2.58, 2.45, 2.333):
            for nsym in (2042, 1900, 1800):
                S = box_for(nsym, cps, mach)
                row.append("M%d n%d cps%.2f -> %dx%d=%d" % (mach, nsym, cps, S, S, S * S))
        print("   " + "  |  ".join(row[:3]))
        print("   " + "  |  ".join(row[3:6]))
        print("   " + "  |  ".join(row[6:]))


if __name__ == "__main__":
    main()
