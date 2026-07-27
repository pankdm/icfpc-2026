#!/usr/bin/env python3
"""Minimum square box for the ring feeder, as a function of the payload bit count.

A feeder row is  | > _ (`D`s)*k _ v |   -> 5 cells of non-payload, U = S-5 usable.
A unit of d digits costs d+3 cells (2 backticks + the `s`) and carries
min(63, d*log2(10)) bits, because a literal must fit in signed 64-bit.
"""
import math

L10 = math.log2(10)


def row_bits(U):
    best = (0, 0, 0)
    for k in range(1, U // 4 + 1):
        d = (U - 3 * k) // k
        if d < 1:
            continue
        b = k * min(63.0, d * L10)
        if b > best[0]:
            best = (b, k, d)
    return best


def solve(B, decoder_rows=9):
    out = []
    for S in range(60, 92):
        U = S - 5
        b, k, d = row_bits(U)
        if b <= 0:
            continue
        R = math.ceil(B / b)
        H = R + decoder_rows
        out.append((max(S, H) ** 2, S, H, R, k, d, round(b, 1)))
    out.sort()
    return out[:4]


print("payload      box    S   H   feedrows  k  d  bits/row")
for name, B in [("current 13601", 13601), ("gzip 12504", 12504),
                ("-5% 12921", 12921), ("-10% 12241", 12241),
                ("-15% 11561", 11561), ("-20% 10881", 10881)]:
    for r in solve(B)[:2]:
        print(f"{name:14s} {r[0]:5d}  {r[1]:3d} {r[2]:3d}  {r[3]:4d}    "
              f"{r[4]:2d} {r[5]:2d}  {r[6]}")
print()
print("row_bits by U:")
for U in (60, 65, 70, 72, 74, 76, 78, 80, 84, 88):
    b, k, d = row_bits(U)
    print(f"  U={U:3d} k={k} d={d:2d} bits/row={b:6.1f}  bits/cell={b/U:.3f}")
