#!/usr/bin/env python3
"""Parameterised brackets assembler: give it a triple, get a graded grid.

Collapses "assemble a 16x16 by hand" to one call. Every room is (w, h, cells,
man); every pipe is placed EXPLICITLY rather than derived from M_w, because
p6_build computes cx = M_w - 6 and then input_room(cx - 5, 13), which lands at
column -1 the moment M_w drops to 10.

Layout contract (the one the 256 enumeration assumes):
    width  = M_w + P_w
    height = max(M_h, P_h) + C_h
    M at (0,0)   P at (M_w,0)   C at (cx,  max(M_h,P_h))

Pipes, all four of them (measured: every room is 1-in/1-out, so bindings cannot
be stolen -- see brk5_bind.py):
    M -> P    P -> O    C -> M    I -> C

usage:
    python3 brk5_asm.py --out /tmp/x.man            # rebuild today's champion
    python3 brk5_asm.py --cw 14 --ch 5 --cx 0 ...   # a candidate triple
"""
import argparse
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'tools'))
sys.path.insert(0, os.path.join(REPO, 'solutions', 'brackets'))
import littleman as lm                                   # noqa: E402
import p6_build as REF                                   # noqa: E402


def block(p, ox, oy, w, h, cells, man):
    p.room(ox, oy, w, h)
    for (x, y, ch) in cells:
        k = (ox + x, oy + y)
        assert p.cells.get(k) in (None, ch), f'collision {k}: {p.cells.get(k)} vs {ch}'
        p.put(k[0], k[1], ch)
    p.man(ox + man[0], oy + man[1])


def assemble(M=(REF.M9_W, REF.M9_H, REF.M9_CELLS, REF.M9_MAN),
             P=(REF.P_W, REF.P_H, REF.P_CELLS, REF.P_MAN),
             C=(REF.C_W, REF.C_H, REF.C_CELLS, REF.C_MAN),
             cx=None, io=None, save='/tmp/brk5.man', verbose=True,
             exit_row=1, entry_row=3):
    Mw, Mh, Mc, Mm = M
    Pw, Ph, Pc, Pm = P
    Cw, Ch, Cc, Cm = C
    band = max(Mh, Ph)                       # C's top row
    cx = (Mw - 6) if cx is None else cx

    p = lm.Program()
    block(p, 0, 0, Mw, Mh, Mc, Mm)
    block(p, Mw, 0, Pw, Ph, Pc, Pm)
    block(p, cx, band, Cw, Ch, Cc, Cm)

    # ---- M -> P, P -> O (unchanged geometry, keyed off Mw/Ph) ----
    p.put(Mw, Ph, '>')
    p.put(Mw + 1, Ph, '^')
    ox, oy = (Mw + 3, Ph) if io is None else io[1]
    p.output_room(ox, oy)
    p.put(Mw + 2, Ph, 'v')
    p.put(Mw + 2, Ph + 1, '>')

    # ---- C -> M and I -> C, placed EXPLICITLY ----
    # exit_row/entry_row are C-INTERIOR rows, so they follow a collapsed C
    # instead of assuming C_H == 6. They must stay strictly inside C.
    assert 1 <= exit_row <= Ch - 2 and 1 <= entry_row <= Ch - 2, \
        f'pipe rows {exit_row},{entry_row} outside a C of height {Ch}'
    assert exit_row != entry_row, 'C exit and entry cannot share a row'
    ex, en = band + exit_row, band + entry_row
    # C's exit leaves its west wall, steps left, climbs to M's bottom wall.
    assert cx >= 2, f'cx={cx} leaves no column for C\'s two west-side pipes'
    p.put(cx - 1, ex, '<')
    p.put(cx - 2, ex, '^')
    for y in range(ex - 1, band - 1, -1):
        p.put(cx - 2, y, '^')
    ix, iy = (cx - 5, band + 2) if io is None else io[0]
    assert ix >= 0 and iy >= 0, f'input room at ({ix},{iy}) is off-grid'
    p.input_room(ix, iy)
    p.put(cx - 2, en, '>')
    p.put(cx - 1, en, '>')

    fp = p.footprint()
    if verbose:
        print(f'M {Mw}x{Mh}  P {Pw}x{Ph}  C {Cw}x{Ch} at cx={cx}  '
              f'-> footprint {fp}')
        exp_w, exp_h = Mw + Pw, band + Ch
        if (fp[0], fp[1]) != (exp_w, exp_h):
            print(f'  NOTE contract says {exp_w}x{exp_h}; margin/pipes exceed it')
    p.save(save)
    return fp


if __name__ == '__main__':
    a = argparse.ArgumentParser()
    a.add_argument('--cw', type=int); a.add_argument('--ch', type=int)
    a.add_argument('--cx', type=int)
    a.add_argument('--out', default='/tmp/brk5.man')
    args = a.parse_args()
    C = (args.cw or REF.C_W, args.ch or REF.C_H, REF.C_CELLS, REF.C_MAN)
    assemble(C=C, cx=args.cx, save=args.out)
