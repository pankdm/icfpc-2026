"""tcp sweep9 — sweep8 geometry with a SHORT checker re-poll rail.

sweep8's idle poll walks a 33-cell detour: from the CI bottom rail (y16) it
rises the whole west column x1 to y0 (16 rows), crosses east 5, then descends
the east corridor x7 to the merge at y8 (8 rows).  The merge only has to be
re-entered heading west at (x7,y8); the fwd-loopback already climbs x7 from
y14.  So the re-poll can turn east one row above the bottom rail (y15) and
join that same riser: 1+1+5+1+7+1 = 16 cells instead of 33.

Everything else is byte-identical to sweep_build7.build_full8.
"""
import sys
import os as _os
_REPO = _os.path.abspath(__file__).split('/solutions/')[0]
sys.path.insert(0, _REPO + '/tools')
sys.path.insert(0, _REPO + '/solutions/tcp')
from layout import Layout, place_pipe, DIRS
from sweep_build import emit_montree


def emit_checker_short(L, cx, cy, attach_j=11, repoll_j=15):
    """9-wide narrow checker (sweep8's folded3) with a short re-poll rail.

    Nearest-pipe note: seq attaches outside the WEST wall and drain outside the
    EAST wall at the SAME row, so only the column decides which is nearest --
    x1..x4 read seq, x5..x7 read drain, at ANY row.  That is what lets the
    bottom rail and the re-poll rail move freely in y.
    """
    x = lambda i: cx + i
    y = lambda j: cy + 1 + j
    # ---- upper main (y1) ----
    L.put(x(1), y(1), '@')
    L.put(x(2), y(1), '>')              # TOP-merge
    L.put(x(3), y(1), 'r')              # seq  (west-nearest)
    L.put(x(4), y(1), '-')              # off = seq - Wt
    L.put(x(6), y(1), 'v')              # glide x5, turn S into pipeline x6
    # ---- shift col x6 ----
    L.put(x(6), y(2), 'b')
    L.put(x(6), y(3), ']'); L.put(x(6), y(4), ']'); L.put(x(6), y(5), ']'); L.put(x(6), y(6), ']')
    # ---- overflow-d (x6,y7); gadget bends down x3 ----
    L.put(x(6), y(7), 'd')
    L.put(x(5), y(7), '1'); L.put(x(4), y(7), 'N'); L.put(x(3), y(7), 'v')
    L.put(x(3), y(8), 's'); L.put(x(3), y(9), 'H')
    # ---- merge (x6,y8) ----
    L.put(x(6), y(8), 'v')
    L.put(x(7), y(8), '<')             # merge entry from east corridor
    # ---- q count drain (x6,y9) ----
    L.put(x(6), y(9), 'q')
    # ---- fwd-d (x6,y10); gadget bends down x3 ----
    L.put(x(6), y(10), 'd')
    L.put(x(5), y(10), 'r'); L.put(x(4), y(10), 's'); L.put(x(3), y(10), 'v')
    L.put(x(3), y(11), '1'); L.put(x(3), y(12), '+'); L.put(x(3), y(13), 'M')
    # loopback rail: (x3,y14)> -> E -> (x7,y14)^ -> up x7 -> merge (x7,y8)<
    L.put(x(3), y(14), '>')
    L.put(x(7), y(14), '^')
    # ---- DP-empty riser: x6 glides y11..y15, turn W ----
    L.put(x(6), y(16), '<')            # bottom rail turn W
    # ---- CI bottom rail (y16) ----
    L.put(x(3), y(16), 'q')            # count seq (west-nearest)
    L.put(x(2), y(16), 'd')            # seq>0 -> CW(W->N) up x2 -> TOP-merge ; seq==0 -> W
    L.put(x(1), y(16), '^')            # seq==0 -> up col1
    # ---- SHORT re-poll: (x1,repoll)> -> E -> (x7,repoll)^ -> joins the x7 riser ----
    L.put(x(1), y(repoll_j), '>')
    L.put(x(7), y(repoll_j), '^')
    # ---- room: 9 wide, 19 tall (rows cy..cy+18) ----
    L.room(cx, cy, 9, 19)
    return {'seqW': (cx - 1, y(attach_j)),
            'drainE': (cx + 9, y(attach_j)),
            'outS': (x(4), cy + 19)}


def build_full9(cy_checker=6, cx_checker=8, attach_row=20, repoll_j=15,
                lane_gap=2, entry_off=15):
    """sweep8 with the short-rail checker."""
    L = Layout()
    CB = 21
    ENTRY = CB + entry_off
    yr = 2
    y0 = yr + 1
    LEAFROW = y0 + 12
    RWX = 17
    # ---- READER ----
    L.put(19, 0, '@'); L.put(20, 0, 'r')
    L.put(21, 0, 'v'); L.put(21, 1, '<')
    L.put(18, 1, 'v')
    L.put(18, yr, '>')
    L.put(19, yr, 'r')
    L.put(20, yr, 'M')
    L.put(21, yr, 's')
    L.put(ENTRY, yr, 'v')
    leaves = emit_montree(L, ENTRY, y0, lambda *a: None)
    for s in range(16):
        c = leaves[s]
        L.put(c, LEAFROW, 'r'); L.put(c, LEAFROW + 1, 's'); L.put(c, LEAFROW + 2, '<')
    L.put(18, LEAFROW + 2, '^')
    RWALL = LEAFROW + 3
    L.room(RWX, -1, (ENTRY + 2) - RWX + 1, RWALL - (-1) + 1)
    L.input_room(12, -1); L.pipe([(15, 0), (16, 0)])

    # ---- LANES ----
    TW = RWALL + lane_gap + 1
    for s in range(16):
        c = leaves[s]
        L.pipe([(c, RWALL + 1), (c, TW - 1)])
    # ---- SWEEPER ----
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

    # ---- CHECKER ----
    cx, cy = cx_checker, cy_checker
    attach_j = attach_row - (cy + 1)
    hints = emit_checker_short(L, cx, cy, attach_j=attach_j, repoll_j=repoll_j)

    # ---- PIPES ----
    seqW = hints['seqW']
    seqcol = cx - 1
    seqrow = seqW[1]
    scells = [(xx, yr) for xx in range(RWX - 1, seqcol - 1, -1)] + \
             [(seqcol, r) for r in range(yr + 1, seqrow + 1)]
    place_pipe(L, scells, exit_dir=DIRS['E'])
    drE = hints['drainE']
    drow = drE[1]
    ecol = drE[0]
    cells = [(SWX - 1, R2)]
    for xx in range(SWX - 2, ecol - 1, -1):
        cells.append((xx, R2))
    for r in range(R2 - 1, drow - 1, -1):
        cells.append((ecol, r))
    place_pipe(L, cells, exit_dir=DIRS['W'])
    outS = hints['outS']
    L.output_room(outS[0] - 1, outS[1] + 2)
    L.pipe([(outS[0], outS[1]), (outS[0], outS[1] + 1)])
    return L


if __name__ == '__main__':
    import sys
    base = _REPO + '/solutions/tcp'
    L = build_full9()
    print('FOOT', L.footprint())
    L.save(base + '/tcp-sweep9.man')
    print('saved')
