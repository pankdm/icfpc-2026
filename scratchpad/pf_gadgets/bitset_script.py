#!/usr/bin/env python3
"""Driver + expected output for bitset256.man.

Exercises set / clear / test at the indices where a 4x64 bitset breaks:

    0    first bit of word 0
    63   the SIGN BIT of word 0   (mask = 1<<63 = -9223372036854775808)
    64   first bit of word 1      (word boundary)
    127  the SIGN BIT of word 1
    255  the SIGN BIT of word 3   (last bit of the board)

Protocol (one transaction = two input values `op i`):
    op 1 -> SET(i)  : emits the mask if the bit was CLEAR, 0 if it was already set
                      (this doubles as the TEST -- non-zero means "newly set")
    op 0 -> CLR(i)  : emits 0

Per index we run  set / set-again / clear / set / clear, then interleave the
indices to prove the four words are independent.
"""
import json
import sys

M64 = (1 << 64) - 1


def s64(v):
    v &= M64
    return v - (1 << 64) if v >> 63 else v


IDX = [0, 63, 64, 127, 255]


def build_case():
    words = [0, 0, 0, 0]
    inp, exp = [], []

    def tx(op, i):
        q, r = divmod(i, 64)
        mask = 1 << r
        inp.extend([str(op), str(i)])
        old = words[q]
        new = old | mask if op == 1 else old
        exp.append(str(s64(old ^ new)))
        words[q] = (new & ~mask) if op == 0 else new

    for i in IDX:                      # per-index lifecycle
        tx(1, i); tx(1, i); tx(0, i); tx(1, i); tx(0, i)
    for i in IDX:                      # cross-word independence: set all
        tx(1, i)
    for i in IDX:                      # all set now -> every answer 0
        tx(1, i)
    for i in IDX:                      # clear all
        tx(0, i)
    for i in IDX:                      # and they are clear again
        tx(1, i)
    return inp, exp


if __name__ == "__main__":
    inp, exp = build_case()
    if "--json" in sys.argv:
        print(json.dumps([{"in": inp, "out": exp}]))
    elif "--count" in sys.argv:
        print(len(inp) // 2)
    else:
        print(" ".join(inp))
        print(" ".join(exp))
