"""tcp sweep20 — 7-row demux (was 12) + init off the west margin: box 729 -> 625.

The box is the driver, and the demux tree was 12 of the 27 rows.  `xtree.py`
replaces emit_montree's 3-rows-per-level (`w` `&` `X`, whose glide exists only on
the SET branch so nothing can ride it) with `x`, a two-way branch in ONE cell
that leaves A and B free and makes BOTH branches glide -- so the next level's
`b`/`]` reloads ride the glides.  MSB-first keeps the tree nested (see xtree.py
for why LSB-first cannot be laid out at all).  Leaf columns are unchanged, so
the lanes, the sweeper and the leaf ops are untouched.

Reader interior, top to bottom:

    yr      entry row: `<` at RAIL, then west 8 with `]` `]` `]` riding the
            glide, `v` at R                       <- the 3 shifts cost 0 rows
    yr+1..7 xtree (7 rows)
    yr+8    leaf `r`(val)
    yr+9    leaf `s` -> lane
    yr+10   east return rail
    yr+11   init row: `@`, `r`(discard n), east to RAIL

Putting the init on its OWN ROW instead of its own two COLUMNS is what takes the
width from 26 to 25 (the sweeper already needs col CB-2, so the reader's west
margin was the only thing pushing the box out).  Height 23, width 25 -> 625.

Climb ops (north, RAIL column): `1` `M` (B=1, re-established every packet, so no
init is needed for it), `r`(seq), `s`(seq->checker), `b` (BP=seq).  They sit at
the TOP of the climb so `s` lands at yr+2 -- the seq pipe's row -- which is what
leaves room for the checker between it and the sweeper.
"""
import sys
import os as _os
_REPO = _os.path.abspath(__file__).split('/solutions/')[0]
sys.path.insert(0, _REPO + '/tools')
sys.path.insert(0, _REPO + '/solutions/tcp')
from layout import Layout, place_pipe, DIRS
from xtree import emit_xtree
from checker_x import emit_checker_x


def build_full21(CB=3, yr=2, gap=0, cy_off=2, lane_gap=2, drain_row_off=4, out_dx=3):
    L = Layout()
    R = CB + 8                           # xtree root; leaves = R+7-slot = CB+15-slot
    y0 = yr + 1
    LEAFROW = y0 + 7
    RAILROW = LEAFROW + 2
    INITROW = RAILROW + 1
    RWALL = INITROW + 1
    RAIL = CB + 16
    REW = RAIL + 1
    RWX = CB - 1

    # ---- READER ----
    leaves = emit_xtree(L, R, y0)
    for s in range(16):
        c = leaves[s]
        L.put(c, LEAFROW, 'r')           # val (input is the room's only incoming pipe)
        L.put(c, LEAFROW + 1, 's')       # -> lane[s]
        L.put(c, RAILROW, '>')           # east return rail
    L.put(RAIL, RAILROW, '^')
    # climb (north): 1 M r s b   -- B=1 is re-established every packet
    L.put(RAIL, yr + 5, '1')
    L.put(RAIL, yr + 4, 'M')
    L.put(RAIL, yr + 3, 'r')             # seq
    L.put(RAIL, yr + 2, 's')             # seq -> checker
    L.put(RAIL, yr + 1, 'b')             # BP = seq
    L.put(RAIL, yr, '<')                 # turn W along the entry row
    for i, ch in enumerate(']]]'):       # the 3 shifts ride the entry glide
        L.put(RAIL - 1 - i, yr, ch)      # BP = seq>>3
    L.put(R, yr, 'v')                    # into the tree
    # init row
    L.put(CB, INITROW, '@')
    L.put(CB + 1, INITROW, 'r')          # discard n (once)
    L.put(RAIL, INITROW, '^')
    L.room(RWX, yr - 1, REW - RWX + 1, RWALL - (yr - 1) + 1)

    # ---- LANES ----
    TW = RWALL + lane_gap + 1
    for s in range(16):
        L.pipe([(leaves[s], RWALL + 1), (leaves[s], TW - 1)])

    # ---- SWEEPER (unchanged) ----
    R0, R1, R2, R3, Rw = TW + 1, TW + 2, TW + 3, TW + 4, TW + 5
    BW = TW + 6
    # Parity flipped vs sweep20: slot 0 is NORTHbound, so the LAST slot exits
    # SOUTHward straight onto the return row and the west wrap column disappears.
    for i in range(16):
        c = CB + 15 - i
        if i % 2 == 0:                   # northbound: enter at R3, exit west at R0
            L.put(c, R3, '^'); L.put(c, R2, 'r'); L.put(c, R1, 's')
            L.put(c, R0, '<')
        else:                            # southbound: enter at R0, exit west at R3
            L.put(c, R0, 'v'); L.put(c, R1, 'r'); L.put(c, R2, 's')
            L.put(c, R3, 'v' if i == 15 else '<')
    ec = CB + 16
    L.put(CB, Rw, '>')                   # last slot drops straight onto the return row
    L.put(ec, Rw, '^'); L.put(ec, R3, '<')
    L.put(CB + 1, Rw, '@')
    SWX = CB - 1
    SEW = CB + 17
    L.room(SWX, TW, SEW - SWX + 1, BW - TW + 1)

    # ---- CHECKER ----
    cx, cy = REW + gap + 1, yr + 2 + cy_off
    hints = emit_checker_x(L, cx, cy)
    scol, nwall = hints['seqN']

    # ---- SEQ PIPE: reader east wall -E-> above the checker -S-> its north wall ----
    srow = yr + 2
    place_pipe(L, [(x, srow) for x in range(REW + 1, scol + 1)] +
                  [(scol, r) for r in range(srow + 1, nwall)], exit_dir=DIRS['S'])

    # ---- INPUT ----
    L.input_room(scol + 1, srow - 2)
    place_pipe(L, [(x, srow - 1) for x in range(scol, REW, -1)], exit_dir=DIRS['W'])

    # ---- DRAIN: sweeper east wall -E-> then N into the checker's south wall ----
    dcol, drow = hints['drainS']
    dr = TW + drain_row_off
    cells = [(x, dr) for x in range(SEW + 1, dcol + 1)] + \
            [(dcol, r) for r in range(dr - 1, drow - 1, -1)]
    place_pipe(L, cells, exit_dir=DIRS['N'])

    # ---- OUTPUT: off the checker's SOUTH wall (north is where the input room sits) ----
    ocol = cx + out_dx
    sw = hints['swall']
    L.output_room(ocol - 1, sw + 3)
    place_pipe(L, [(ocol, sw + 1), (ocol, sw + 2)], exit_dir=DIRS['S'])
    return L


if __name__ == '__main__':
    base = _REPO + '/solutions/tcp'
    L = build_full21()
    print('FOOT', L.footprint())
    L.save(base + '/tcp-sweep21.man')
    print('saved')
