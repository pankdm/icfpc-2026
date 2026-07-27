"""tcp: sweep8 reader+sweeper with the compact checker from tight_checker.py."""
import os as _os
_REPO = _os.path.abspath(__file__).split('/solutions/')[0]
import sys
sys.path.insert(0, _REPO + '/tools')
sys.path.insert(0, _REPO + '/solutions/tcp')
from layout import Layout, place_pipe, DIRS
from sweep_build import emit_montree
from tight_checker import emit_checker_tight


def emit_orig_reader(L, ENTRY, RWX, yr=2):
    """sweep8's reader: loop at row yr, montree, leaf r/s, west rail + riser."""
    y0 = yr + 1
    LEAFROW = y0 + 12
    L.put(RWX + 2, 0, '@'); L.put(RWX + 3, 0, 'r')
    L.put(RWX + 4, 0, 'v'); L.put(RWX + 4, 1, '<')
    L.put(RWX + 1, 1, 'v')
    L.put(RWX + 1, yr, '>')
    L.put(RWX + 2, yr, 'r')
    L.put(RWX + 3, yr, 'M')
    L.put(RWX + 4, yr, 's')
    L.put(ENTRY, yr, 'v')
    leaves = emit_montree(L, ENTRY, y0, lambda *a: None)
    for s in range(16):
        c = leaves[s]
        L.put(c, LEAFROW, 'r'); L.put(c, LEAFROW + 1, 's'); L.put(c, LEAFROW + 2, '<')
    L.put(RWX + 1, LEAFROW + 2, '^')
    return LEAFROW + 3, leaves


def emit_sweeper(L, CB, TW):
    R0, R1, R2, R3, Rw = TW + 1, TW + 2, TW + 3, TW + 4, TW + 5
    BW = TW + 6
    for i in range(16):
        c = CB + 15 - i
        if i % 2 == 0:
            L.put(c, R0, 'v'); L.put(c, R1, 'r'); L.put(c, R2, 's')
            if i != 15: L.put(c, R3, '<')
        else:
            L.put(c, R3, '^'); L.put(c, R2, 'r'); L.put(c, R1, 's')
            if i != 15: L.put(c, R0, '<')
    L.put(CB, R0, '<')
    wc = CB - 1; ec = CB + 16
    L.put(wc, R0, 'v'); L.put(wc, Rw, '>')
    L.put(ec, Rw, '^'); L.put(ec, R0, '<')
    L.put(wc + 1, Rw, '@')
    SWX = CB - 2
    L.room(SWX, TW, (CB + 17) - SWX + 1, BW - TW + 1)
    return SWX, R2


def build(cx_checker=8, cy_checker=6, RWX=17, east_slack=2):
    L = Layout()
    CB = 21
    ENTRY = CB + 15
    yr = 2
    RWALL, leaves = emit_orig_reader(L, ENTRY, RWX, yr)
    L.room(RWX, -1, (ENTRY + east_slack) - RWX + 1, RWALL - (-1) + 1)
    L.input_room(RWX - 5, -1); L.pipe([(RWX - 2, 0), (RWX - 1, 0)])

    TW = RWALL + 3
    for s in range(16):
        L.pipe([(leaves[s], RWALL + 1), (leaves[s], TW - 1)])
    SWX, R2 = emit_sweeper(L, CB, TW)

    cx, cy = cx_checker, cy_checker
    hints = emit_checker_tight(L, cx, cy)

    seqrow = hints['seqW'][1]
    seqcol = cx - 1
    scells = [(xx, yr) for xx in range(RWX - 1, seqcol - 1, -1)] + \
             [(seqcol, r) for r in range(yr + 1, seqrow + 1)]
    place_pipe(L, scells, exit_dir=DIRS['E'])
    dcol, drow = hints['drainS']
    cells = [(xx, R2) for xx in range(SWX - 1, dcol - 1, -1)] + \
            [(dcol, r) for r in range(R2 - 1, drow - 1, -1)]
    place_pipe(L, cells, exit_dir=DIRS['N'])
    outS = hints['outS']
    L.output_room(outS[0] - 1, outS[1] + 2)
    L.pipe([(outS[0], outS[1]), (outS[0], outS[1] + 1)])
    return L


if __name__ == '__main__':
    L = build()
    print('FOOT', L.footprint())
    L.save(_REPO + '/solutions/tcp/tcp-tight1.man')
    print('saved tcp-tight1.man')
