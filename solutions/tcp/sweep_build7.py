"""tcp sweep7 — narrower checker (emit_checker_folded2): 10 wide vs 12.

PURE GEOMETRIC fold of the folded checker. Same LETTER-op multiset
(r,s,M,b,d,q,N,H) — only arrows / digits / pipe-`v` change.

Lower-main folded VERTICAL into a single pipeline column (x7):
  merge(v) -> q -> fwd-d -> DP-empty(S).  Overflow + fwd gadgets branch WEST
  into the free rows of x1..x6.  All risers (re-poll, loopback, CI re-read)
  run up the CLEAR east corridor x8 / far-west x1 / x2 so they never cross a
  gadget row.  seq(west) + drain(east) attach at the SAME row (y9) so the
  y-distance cancels and pure x-position decides nearest: west reads (r,q at
  x3) -> seq, east reads (fwd-r x6, q x7) -> drain.
"""
import sys
import os as _os
_REPO = _os.path.abspath(__file__).split('/solutions/')[0]
sys.path.insert(0, _REPO + '/tools')
sys.path.insert(0, _REPO + '/solutions/tcp')
from layout import Layout, place_pipe, DIRS
from sweep_build import emit_montree


def emit_checker_folded2(L, cx, cy):
    """Narrow folded checker: 10 wide (interior x1..x8), ~18 tall.
    Returns {'seqW','drainE','outS'} attach hints."""
    x = lambda i: cx + i
    y = lambda j: cy + 1 + j            # y(0) = first interior row; cy = north wall
    # ---- upper main (y1) ----
    L.put(x(1), y(1), '@')
    L.put(x(2), y(1), '>')              # TOP-merge (re-read-seq path merges)
    L.put(x(3), y(1), 'r')              # read seq  (west-nearest -> seq)
    L.put(x(4), y(1), '-')              # off = seq - Wt
    L.put(x(7), y(1), 'v')              # glide x5,x6 then turn S into pipeline col x7
    # ---- shift column x7 ----
    L.put(x(7), y(2), 'b')              # bp = off
    L.put(x(7), y(3), ']'); L.put(x(7), y(4), ']'); L.put(x(7), y(5), ']'); L.put(x(7), y(6), ']')
    # ---- overflow-d (x7,y7) ; gadget branches WEST ----
    L.put(x(7), y(7), 'd')              # bp>0 (off>=16) -> CW(S->W) overflow ; else S
    L.put(x(6), y(7), '1'); L.put(x(5), y(7), 'N'); L.put(x(4), y(7), 's'); L.put(x(3), y(7), 'H')
    # ---- merge (x7,y8) ----
    L.put(x(7), y(8), 'v')              # S-through (overflow-straight) + side entry
    L.put(x(8), y(8), '<')             # merge entry from east corridor (re-poll / loopback)
    # ---- q count drain (x7,y9) ----
    L.put(x(7), y(9), 'q')             # east-nearest -> drain
    # ---- fwd-d (x7,y10) ; gadget branches WEST ----
    L.put(x(7), y(10), 'd')            # bp>0 (drain avail) -> CW(S->W) fwd ; else S (DP-empty)
    L.put(x(6), y(10), 'r')            # recv drain val (east-nearest -> drain)
    L.put(x(5), y(10), 's')            # send val -> output
    L.put(x(4), y(10), '1')
    L.put(x(3), y(10), 'v')            # bend S
    L.put(x(3), y(11), '+')            # A = 1 + Wt
    L.put(x(3), y(12), 'M')            # B = Wt+1
    # loopback rail: (x3,y13)> -> E -> (x8,y13)^ -> up x8 -> merge (x8,y8)<
    L.put(x(3), y(13), '>')
    L.put(x(8), y(13), '^')
    # ---- DP-empty riser: x7 glides y11..y14, turn W at bottom ----
    L.put(x(7), y(15), '<')            # bottom rail turn W
    # ---- CI bottom rail (y15) ----
    L.put(x(3), y(15), 'q')            # count seq (west-nearest -> seq)
    L.put(x(2), y(15), 'd')            # seq>0 -> CW(W->N) up x2 -> TOP-merge ; seq==0 -> W
    L.put(x(1), y(15), '^')            # seq==0 -> up col1 (re-poll)
    # ---- re-poll: (x1,y0)> -> E -> (x8,y0)v -> down x8 -> merge ----
    L.put(x(1), y(0), '>')
    L.put(x(8), y(0), 'v')
    # ---- room: 10 wide, 18 tall (rows cy..cy+17) ----
    L.room(cx, cy, 10, 18)
    return {'seqW': (cx - 1, y(9)),                 # west wall attach row y9
            'drainE': (cx + 10, y(9)),              # east wall attach row y9
            'outS': (x(4), cy + 18)}                # south wall (any interior col)


def emit_checker_folded3(L, cx, cy, attach_j=11):
    """9-wide narrow checker: pipeline in col x6, corridor x7, gadgets bent to
    end at x3 so the CI-seq riser (x2) stays clear.  Interior x1..x7 -> room 9
    wide.  seq(west)/drain(east) attach at SAME row y(attach_j)."""
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
    L.put(x(1), y(16), '^')            # seq==0 -> up col1 (re-poll)
    # ---- re-poll: (x1,y0)> -> E -> (x7,y0)v -> down x7 -> merge ----
    L.put(x(1), y(0), '>')
    L.put(x(7), y(0), 'v')
    # ---- room: 9 wide, 19 tall (rows cy..cy+18) ----
    L.room(cx, cy, 9, 19)
    return {'seqW': (cx - 1, y(attach_j)),
            'drainE': (cx + 9, y(attach_j)),
            'outS': (x(4), cy + 19)}


def build_full8(cy_checker=6, cx_checker=8, attach_row=20):
    """build_full7 with the 9-wide checker (folded3) -> width 32."""
    L = Layout()
    CB = 21
    ENTRY = CB + 15
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
    TW = RWALL + 3
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

    # ---- CHECKER (narrow folded3) ----
    cx, cy = cx_checker, cy_checker
    attach_j = attach_row - (cy + 1)
    hints = emit_checker_folded3(L, cx, cy, attach_j=attach_j)

    # ---- PIPES ----
    seqW = hints['seqW']
    seqcol = cx - 1
    seqrow = seqW[1]
    scells = [(xx, yr) for xx in range(RWX - 1, seqcol - 1, -1)] + \
             [(seqcol, r) for r in range(yr + 1, seqrow + 1)]
    place_pipe(L, scells, exit_dir=DIRS['E'])
    drE = hints['drainE']
    drow = drE[1]
    ecol = drE[0]                       # vertical leg == drE column (exits W into east wall)
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


def build_full7(cy_checker=12, cx_checker=7):
    """build_full6 geometry with the narrow checker (folded2)."""
    L = Layout()
    CB = 21
    ENTRY = CB + 15
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
    TW = RWALL + 3
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

    # ---- CHECKER (narrow folded2) ----
    cx, cy = cx_checker, cy_checker
    hints = emit_checker_folded2(L, cx, cy)

    # ---- PIPES ----
    # seq: reader west wall (RWX-1,yr) -> W along row yr to col cx-1 -> DOWN col cx-1
    #      -> BEND E into checker west wall at seq row.
    seqW = hints['seqW']                            # (cx-1, seqrow)
    seqcol = cx - 1
    seqrow = seqW[1]
    scells = [(xx, yr) for xx in range(RWX - 1, seqcol - 1, -1)] + \
             [(seqcol, r) for r in range(yr + 1, seqrow + 1)]
    place_pipe(L, scells, exit_dir=DIRS['E'])
    # drain: sweeper west wall -> gap -> up -> W into checker EAST wall
    drE = hints['drainE']                           # (cx+10, drow) = one E of east wall
    drow = drE[1]
    ecol = cx + 10                                  # vertical leg just EAST of checker east wall
    # sweeper west wall (SWX-1,R2) -> W to ecol -> up ecol to drow -> W into checker east wall
    cells = [(SWX - 1, R2)]
    for xx in range(SWX - 2, ecol - 1, -1):
        cells.append((xx, R2))
    for r in range(R2 - 1, drow - 1, -1):
        cells.append((ecol, r))
    place_pipe(L, cells, exit_dir=DIRS['W'])
    # output: checker south -> O below
    outS = hints['outS']
    L.output_room(outS[0] - 1, outS[1] + 2)
    L.pipe([(outS[0], outS[1]), (outS[0], outS[1] + 1)])
    return L


if __name__ == '__main__':
    import sys
    base = _REPO + '/solutions/tcp'
    if '--v7' in sys.argv:                       # 33x33 folded2 checker
        L = build_full7(cy_checker=9)
        out = base + '/tcp-sweep7.man'
    else:                                        # 32x31 folded3 checker (best)
        L = build_full8(cy_checker=6, attach_row=20)
        out = base + '/tcp-sweep8.man'
    print('FOOT', L.footprint())
    L.save(out)
    print('saved', out)
