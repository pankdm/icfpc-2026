#!/usr/bin/env python3
"""Exact base-92 capacity model for the ring feeder.

A slot of d decimal digits costs d+3 cells (2 backticks + its `s`) and holds
n base-92 symbols where 92^n <= min(10^d, 2^63).  Row capacity is a knapsack
over slot widths for the usable width U; the grid is (U+5) wide and
(rows + DEC) tall, so the box is max(U+5, rows+DEC)^2.
"""
import math, sys

B = 92
MAXSYM = 1
while B ** (MAXSYM + 1) < 2 ** 63:
    MAXSYM += 1                      # 9


def syms_for_digits(d):
    if d < 1:
        return 0
    n = 0
    while n < MAXSYM and B ** (n + 1) <= 10 ** d and B ** (n + 1) < 2 ** 63:
        n += 1
    return n


CELL = {d: d + 3 for d in range(1, 20)}
SYM = {d: syms_for_digits(d) for d in range(1, 20)}


def row_syms(U):
    """best symbols in a row of usable width U (unbounded knapsack)."""
    best = [0] * (U + 1)
    pick = [None] * (U + 1)
    for u in range(1, U + 1):
        for d in range(1, 20):
            c = CELL[d]
            if c <= u and best[u - c] + SYM[d] > best[u]:
                best[u] = best[u - c] + SYM[d]
                pick[u] = d
    slots, u = [], U
    while u and pick[u]:
        slots.append(pick[u]); u -= CELL[pick[u]]
    return best[U], sorted(slots, reverse=True)


def solve(total_syms, dec_rows=9, over=5):
    out = []
    for S in range(60, 90):
        U = S - over
        if U < 5:
            continue
        n, slots = row_syms(U)
        if n == 0:
            continue
        rows = math.ceil(total_syms / n)
        H = rows + dec_rows
        out.append((max(S, H) ** 2, S, H, rows, n, tuple(slots)))
    out.sort()
    return out


if __name__ == "__main__":
    print("MAXSYM", MAXSYM, " sym/digits:",
          {d: SYM[d] for d in (10, 12, 14, 15, 16, 17, 18, 19)})
    print("\nrow capacity by usable width U:")
    for U in range(58, 84, 2):
        n, sl = row_syms(U)
        print(f"  U={U:3d}  syms={n:3d}  {n/U:.4f}/cell  slots={sl}")
    print("\nbest square box vs total symbol count (dec_rows=9):")
    for tot in (2042, 2100, 1950, 1850, 1750, 1650, 1550, 1450):
        r = solve(tot)[0]
        print(f"  syms={tot:5d} -> box {r[0]:5d}  ({r[1]}w x {r[2]}h) "
              f"rows={r[3]} sym/row={r[4]} slots={r[5]}")
