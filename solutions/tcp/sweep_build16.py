"""tcp sweep11 — checker moved EAST of the reader, collapsing the reader loop.

MEASURED on sweep8 (block-reversed n=32, 40% of avgTicks): the reader man burns
~40 of ~69 ticks per packet on pure travel.  The cause is geometric:

  * emit_montree is monotone WEST (`X`: A>0 -> CW; heading S, CW = W), so its
    ENTRY is the EAST end of the 16 leaf columns;
  * `s`(seq) must beat the 16 lane pipes on the south wall to reach the seq
    pipe, which pins it within ~16 columns of the WEST wall.

So every packet walks west-wall -> east-entry (18 cells) and back (15-row climb
+ ~10-cell west rail).  Putting the CHECKER east of the reader attaches the seq
pipe to the reader's EAST wall; then `s`(seq) sits one column east of the tree
entry and the return rail runs EAST (short) instead of WEST.

  reader loop: ~32 + 2*slot ticks   (sweep8: ~54 + 2*slot)

No checker internals change -- only the floorplan and the reader rail.  The
drain pipe now has to wrap around the checker (23 cells vs 6), which costs
~17 ticks of latency on every output-producing round; that is deliberate.  The
SEQ pipe stays short, and that is the one that matters for safety: an
over-delayed packet (seq >= Wt+16) whose slot aliases Wt would be drained and
forwarded as a real value, so the checker's `-1`+`H` must win the race against
reader-tree -> lane -> sweeper -> drain.  Short seq / long drain widens that
margin; the mirrored floorplan (short drain, long seq) would narrow it.
"""
import sys
import os as _os
_REPO = _os.path.abspath(__file__).split('/solutions/')[0]
sys.path.insert(0, _REPO + '/tools')
sys.path.insert(0, _REPO + '/solutions/tcp')
from layout import Layout, place_pipe, DIRS
from sweep_build import emit_montree
from sweep_build7 import emit_checker_folded3
from checker_u5n import emit_checker_u5n


def build_full16(CB=3, yr=2, gap=1, cy_checker=5,
                 lane_gap=2, drain_row_off=3, seq_row_off=1, out_dx=3):
    L = Layout()
    ENTRY = CB + 15                      # montree entry = EAST end of the leaves
    y0 = yr + 1
    LEAFROW = y0 + 12
    RWALL = LEAFROW + 3                  # reader south wall
    RAIL = ENTRY + 1                     # east return-rail column
    REW = RAIL + 1                       # reader east wall
    RWX = CB - 3                         # reader west wall (2 free west columns)

    # ---- READER ----
    leaves = emit_montree(L, ENTRY, y0, lambda *a: None)
    for s in range(16):
        c = leaves[s]
        L.put(c, LEAFROW, 'r')           # val  (input is the room's only incoming pipe)
        L.put(c, LEAFROW + 1, 's')       # -> lane[s]
        L.put(c, LEAFROW + 2, '>')       # east return rail
    L.put(RAIL, LEAFROW + 2, '^')        # turn N, climb the east rail
    sq = yr + seq_row_off                # the `s`(seq) row == the seq pipe's row
    L.put(RAIL, sq + 2, 'r')             # seq
    L.put(RAIL, sq + 1, 'M')             # B = seq
    L.put(RAIL, sq, 's')                 # seq -> checker (straight 2-cell east pipe)
    L.put(RAIL, yr, '<')                 # turn W into the tree entry
    L.put(ENTRY, yr, 'v')                # tree entry
    L.put(RWX + 1, LEAFROW + 2, '@')     # init: walks E along the rail
    L.put(RWX + 2, LEAFROW + 2, 'r')     # discard n (once)
    L.room(RWX, yr - 1, REW - RWX + 1, RWALL - (yr - 1) + 1)

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
    SEW = CB + 17                        # sweeper east wall
    L.room(SWX, TW, SEW - SWX + 1, BW - TW + 1)

    # ---- CHECKER (east of the reader; internals unchanged) ----
    cx, cy = REW + gap + 1, cy_checker   # gap free columns between reader and checker
    hints = emit_checker_u5n(L, cx, cy)
    scol, nwall = hints['seqN']          # seq must flow SOUTH into the north wall

    # ---- SEQ PIPE: reader east wall -E-> across the gap -S-> checker north wall.
    # The final segment MUST be southward: `U` faces the man along the pipe's flow
    # direction and the engine derives that from the last two PATH cells.
    srow = yr + seq_row_off
    place_pipe(L, [(x, srow) for x in range(REW + 1, scol + 1)] +
                  [(scol, r) for r in range(srow + 1, nwall)], exit_dir=DIRS['S'])

    # ---- INPUT: room east of the checker's column band, above it ----
    L.input_room(scol + 1, srow - 2)     # 3x3, rows srow-2..srow
    place_pipe(L, [(x, srow - 1) for x in range(scol, REW, -1)], exit_dir=DIRS['W'])

    # ---- DRAIN: sweeper east wall -E-> under the checker -N-> checker SOUTH wall.
    # South (not east) so no riser column is needed east of the checker: that is the
    # column that decides the box.  Legal because the checker's nearest-pipe tests
    # only compare seq(west) vs drain, and with seq at y(16) / drain at x(7) every
    # test still resolves the same way (margins 2,2,4,2).
    dcol, drow = hints['drainS']
    dr = TW + drain_row_off
    cells = [(x, dr) for x in range(SEW + 1, dcol + 1)] + \
            [(dcol, r) for r in range(dr - 1, drow - 1, -1)]
    place_pipe(L, cells, exit_dir=DIRS['N'])

    # ---- OUTPUT: off the checker's NORTH wall (only outgoing pipe -> `s` is free) ----
    ocol = cx + out_dx
    sw = hints['swall']
    L.output_room(ocol - 1, sw + 3)      # rows sw+3..sw+5, clear of the drain row
    place_pipe(L, [(ocol, sw + 1), (ocol, sw + 2)], exit_dir=DIRS['S'])
    return L


if __name__ == '__main__':
    base = _REPO + '/solutions/tcp'
    L = build_full16()
    print('FOOT', L.footprint())
    L.save(base + '/tcp-sweep16.man')
    print('saved')
