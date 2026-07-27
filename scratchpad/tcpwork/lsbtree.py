#!/usr/bin/env python3
"""MEASURE the collision that blocks a register-free (LSB-first) demux.

The read loop's 24-tick period is a required ORDERING DELAY: the clone must
reach its `r`(val) before the main man reads the next `seq`. Killing the delay
needs `val` carried through the decode, which needs BOTH A and B free, which
needs a decode that uses only BP -- i.e. `x`/`]` with NO `b` reloads, i.e.
LSB-first.

LSB-first fixes the level magnitudes: leaf = base + sum m_i*(1-2*b_i), so bit i
gets coefficient 2*m_i. Monotone contiguous lanes need coefficients 1,2,4,8 for
bits 0,1,2,3. 2*m_0 = 1 is impossible, so bit0 must be the user's gadget
(displacement 0/-1, coefficient 1) and bits 1,2,3 take coefficients 2,4,8 ->
magnitudes 1,2,4 -- consumed in that order, i.e. INCREASING.

Increasing magnitudes are what collide: a level's glide lands on cells its own
siblings occupy in the same row. This script emits the tree and reports the
exact cells, so the blocker is measured rather than asserted.
"""


def build(E=100, y0=0, mags=(1, 2, 4)):
    """LSB-first: x on bit1 (mags[0]), bit2 (mags[1]), bit3 (mags[2])."""
    cells = {}
    hits = []

    def put(x, y, ch, who):
        if (x, y) in cells and cells[(x, y)][0] != ch:
            hits.append((x, y, cells[(x, y)], (ch, who)))
        else:
            cells[(x, y)] = (ch, who)

    nodes = [E]
    row = y0
    for lvl, m in enumerate(mags):
        nxt = []
        for c in nodes:
            put(c, row, 'x', f'L{lvl}node')
            for s in (+1, -1):                 # x always turns: both branches glide
                for k in range(1, m):
                    put(c + k * s, row, ' ', f'L{lvl}glide')
                put(c + m * s, row, 'v', f'L{lvl}turn')
                nxt.append(c + m * s)
        nodes = nxt
        row += 1
        for c in nodes:                        # `]` between levels
            put(c, row, ']', f'L{lvl}shift')
        row += 1
    return cells, hits, nodes


def main():
    cells, hits, leaves = build()
    print(f"LSB-first, magnitudes 1,2,4 (the only assignment giving monotone lanes)")
    print(f"level-2 node columns: {sorted(set(leaves))[:8]} ...")
    if not hits:
        print("no collisions")
        return
    print(f"COLLISIONS: {len(hits)}")
    for x, y, old, new in hits[:6]:
        print(f"  cell ({x},{y}): {old[1]} wants {old[0]!r}, {new[1]} wants {new[0]!r}")
    # what it would cost to dodge: give each colliding subtree its own row
    print()
    print("dodge = one row per node at the colliding level:")
    print("  level 2 has 2 nodes -> 2 rows, level 3 has 4 nodes -> 4 rows")
    print("  tree rows 7 -> 7 + (2-1) + (4-1) = 11, plus the bit0 gadget's 6 = 17")
    print("  against today's 7-row tree + 3 (r,s,H) = 10  ->  +7 rows")


main()
