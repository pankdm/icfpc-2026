#!/usr/bin/env python3
"""Backpack-indexed positioner (ICFPC-2026 littleman) -- reusable "drop-at-column-k".

A single man carries index k in its BACKPACK (b bits). It enters the top of a
compact binary-deflection tree heading SOUTH and, level by level, reads one BP bit
with `x` and deflects HORIZONTALLY (east/west), landing on one of 2^b bottom-row
columns. This is the *transpose* of the vertical decoder16 tree: the forward axis
(south) stays compact (~b+1 rows) while the leaves spread along COLUMNS.

Op mechanics (confirmed against interp/src/lib.rs):
  * heading SOUTH, `x` : BP low bit == 1 -> CW  -> WEST ; bit == 0 -> CCW -> EAST.
  * `]`               : BP := BP >> 1  (advance to next bit) -- placed ONCE per level
                         on the horizontal deflection run, EXCEPT the last level.
  * `b`               : BP := A         (load the index).
  * `r`               : A  := read nearest input pipe.
  * `v`               : turn back SOUTH after the horizontal walk (turn-back arrow).
  * `H`               : halt (the leaf marker -- final man column == chosen slot).

Per level i the man enters a node cell (col,row) heading south:
  - place `x` at (col,row).
  - bit0 branch: deflect EAST by E[i]; bit1 branch: deflect WEST by F[i].
  - the `]` sits on the first deflected cell (col +/-1, row) for every non-final level.
  - a `v` at the corner (col +/- disp, row) turns the man back south.
  - the child node sits one row below that corner  => GAP = 1 row per level.
Leaf column offset = sum_i (bit_i ? -F[i] : +E[i]).

Two weight modes:
  * SIGNED  (E[i]=F[i]=2^(b-1-i)) -> a clean symmetric tree. Because both branches
    move >=1 in OPPOSITE directions, the leaf columns are all the SAME parity =>
    spacing 2 => width 2^(b+1)-1 (NOT 2^b). This is a hard geometric floor of the
    x-deflection: the LSB level cannot achieve spacing 1.
  * MIXED   (asymmetric E[i]!=F[i]) -> break the parity to pack the leaves tighter.
    Uses per-level swings g[i]=E[i]+F[i] whose subset sums are 16 distinct values;
    minimal span search gives width ~ 2^b+2 (still > 2^b, floor g_i>=2).
"""
import argparse, os, sys
sys.path.insert(0, '/Users/visenbaev/icfpc26/tools')
from littleman import Program


def signed_weights(b):
    W = [1 << (b - 1 - i) for i in range(b)]      # 8,4,2,1 for b=4
    return [(w, w) for w in W]                     # (E_i, F_i)


def mixed_weights(b):
    """Asymmetric (E,F) per level so leaf columns pack tighter than spacing-2.
    Only defined for b=4 here (the interesting case); falls back to signed."""
    if b == 4:
        # swings g=E+F = [8,4,3,2] -> subset sums {0..17} 16 distinct (span 18).
        # bit0 -> +E east, bit1 -> -F west.  Pick E,F>=1 summing to g.
        #   g=8 -> E=5,F=3 ; g=4 -> E=2,F=2 ; g=3 -> E=2,F=1 ; g=2 -> E=1,F=1
        return [(5, 3), (2, 2), (2, 1), (1, 1)]
    return signed_weights(b)


def leaf_offset(k, weights):
    off = 0
    for i, (E, F) in enumerate(weights):
        bit = (k >> i) & 1
        off += (-F) if bit == 1 else (+E)
    return off


def build(b, mode='signed'):
    weights = signed_weights(b) if mode == 'signed' else mixed_weights(b)
    offs = [leaf_offset(k, weights) for k in range(1 << b)]
    minoff, maxoff = min(offs), max(offs)

    p = Program()
    ROOM_TOP = 0
    ENTRY = 1                       # man preamble row (inside room)
    YC = [2 + i for i in range(b)]  # decision row per level, GAP=1
    LEAF_ROW = YC[-1] + 1
    ROOM_BOT = LEAF_ROW + 1

    # centre column so leftmost leaf sits at interior col 2 (>=1 off the west wall).
    C0 = 2 - minoff
    right_leaf = C0 + maxoff
    ROOM_RIGHT = right_leaf + 2      # right wall 1 clear col past rightmost leaf
    # ROOM_RIGHT is the x of the east wall; interior must also clear the entry run.
    ROOM_RIGHT = max(ROOM_RIGHT, C0 + 2)
    W_ROOM = ROOM_RIGHT + 1

    # ---- enclosing room (west wall col 0) ----
    p.room(0, ROOM_TOP, W_ROOM, ROOM_BOT - ROOM_TOP + 1)

    # ---- input room + 2-cell pipe into the west wall at ENTRY row ----
    p.input_room(-5, ROOM_TOP)                     # I at (-4,ENTRY) when ROOM_TOP=0 -> (-4,1)
    p.pipe([(-2, ENTRY), (-1, ENTRY)])             # back nbr (-3,ENTRY)=I east wall; fwd (0,ENTRY)=main wall

    # ---- preamble: @ r b placed ADJACENT to the tree centre (no long entry glide) ----
    # man reads the (only) input pipe with `r` regardless of distance to its attach.
    p.put(C0 - 3, ENTRY, '@'); p.put(C0 - 2, ENTRY, 'r'); p.put(C0 - 1, ENTRY, 'b')
    p.put(C0, ENTRY, 'v')                          # turn south to enter the tree

    leaf_col = {}

    def node(level, col, row):
        p.put(col, row, 'x')
        for bit in (0, 1):
            if bit == 0:
                sgn, disp = +1, weights[level][0]      # east E
            else:
                sgn, disp = -1, weights[level][1]      # west F
            if level < b - 1:
                p.put(col + sgn, row, ']')             # shift BP once (non-final levels)
            corner = col + sgn * disp
            p.put(corner, row, 'v')                    # turn back south
            if level < b - 1:
                node(level + 1, corner, row + 1)
            else:
                p.put(corner, LEAF_ROW, 'H')           # leaf marker

    node(0, C0, YC[0])

    # record k -> expected leaf column
    for k in range(1 << b):
        leaf_col[k] = C0 + leaf_offset(k, weights)
    return p, leaf_col, weights, C0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-b', type=int, default=4)
    ap.add_argument('--mode', choices=['signed', 'mixed'], default='signed')
    ap.add_argument('-o', '--out', default=None)
    args = ap.parse_args()
    p, leaf_col, weights, C0 = build(args.b, args.mode)
    out = args.out or f'/Users/visenbaev/icfpc26/scratchpad/positioner/pos{args.b}_{args.mode}.man'
    p.save(out)
    w, h, box = p.footprint()
    cols = [leaf_col[k] for k in range(1 << args.b)]
    print(f'built {out}')
    print(f'  b={args.b} mode={args.mode} weights={weights} C0={C0}')
    print(f'  full footprint (with I/O): {w}x{h} box={box}')
    print(f'  expected k->col: {leaf_col}')
    print(f'  distinct cols: {len(set(cols))}/{1<<args.b}  span={max(cols)-min(cols)+1}')


if __name__ == '__main__':
    main()
