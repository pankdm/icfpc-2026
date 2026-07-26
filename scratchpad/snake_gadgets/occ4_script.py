#!/usr/bin/env python3
"""Test script + expected output for occ4.man (Python model of the 4 words)."""
M64 = (1 << 64) - 1
def s64(v):
    v &= M64
    return v - (1 << 64) if v >> 63 else v

words = [0, 0, 0, 0]
inp, exp = [], []

def tx(op, i):                       # op 1 = SET(+test), 0 = CLR
    q, r = divmod(i, 64)
    mask = 1 << r
    inp.extend([str(op), str(i)])
    old = words[q]
    if op == 1:
        new = old | mask
    else:
        new = old
    exp.append(str(s64(old ^ new)))
    words[q] = (new & ~mask) if op == 0 else new

IDX = [0, 63, 64, 255]
for i in IDX:                        # per-index: set / re-set / clear / set / clear
    tx(1, i); tx(1, i); tx(0, i); tx(1, i); tx(0, i)
for i in IDX:                        # cross-quarter independence
    tx(1, i)
for i in IDX:
    tx(1, i)                         # all now occupied -> all 0
for i in IDX:
    tx(0, i)

if __name__ == '__main__':
    import json, sys
    if '--json' in sys.argv:
        print(json.dumps([{"in": inp, "out": exp}]))
    else:
        print(' '.join(inp))
        print(' '.join(exp))
