"""tcp fork design — reader loop replaced by a Y-forked, halt-at-leaf worker.

The sweep8 reader walked a full circuit every round: east to the tree entry,
12 rows down the montree, then ~16 west + ~15 north back to the loop entry
(~64 ticks/round, and the return leg is on the critical path because the next
round's input is released as soon as the current round's output settles).

Here the reader room holds a tiny LOOPER that never leaves rows 0-2 and forks a
fresh WORKER per round; the worker reads seq, forwards it, walks the montree,
reads val, drops it in the lane and HALTS.  No return leg at all.

Gate (rings on rows 0/1) sequences the fork so exactly one worker is alive per
round and it, not the looper, consumes the input:
  ring1: spin until q(input) == 0   (previous worker took seq AND val)
  ring2: spin until q(input) >= 2   (this round's seq+val are both in the pipe)
  then Y: east copy = worker, west copy = looper -> back to ring1.
"""
import os as _os
_REPO = _os.path.abspath(__file__).split('/solutions/')[0]
import sys
sys.path.insert(0, _REPO + '/tools')
sys.path.insert(0, _REPO + '/solutions/tcp')
from layout import Layout, place_pipe, DIRS
from sweep_build import emit_montree
from sweep_build7 import emit_checker_folded3


def emit_fork_reader(L, ET, y0):
    """Reader interior spans columns ET-16..ET+1, rows 0..(y0+15).
    Returns (RWALL, west_interior_col, leaves)."""
    r0, r1, r2 = 0, 1, 2                     # gate return / gate main / worker row
    g = lambda i: ET - 16 + i                # gate columns g(0)..g(7)

    # ---- ring 1: spin while q(input) > 0 ----
    L.put(g(0), r1, '>')                     # merge (from ring1 return, and looper)
    L.put(g(1), r1, 'q')
    L.put(g(2), r1, 'a')                     # BP>0 -> CCW(E->N) = loop ; BP==0 -> E
    L.put(g(2), r0, '<')
    L.put(g(1), r0, '<')
    L.put(g(0), r0, 'v')                     # -> (g0,r1) '>'

    # ---- ring 2: spin while q(input) < 2 ----
    L.put(g(3), r1, '>')                     # merge (from ring2 return)
    L.put(g(4), r1, 'q')
    L.put(g(5), r1, ']')                     # BP = depth>>1 ; >0 iff depth >= 2
    L.put(g(6), r1, 'd')                     # BP>0 -> CW(E->S) = fork ; BP==0 -> E
    L.put(g(7), r1, '^')                     # loop: up into the return lane
    for i in range(3, 8):
        L.put(g(i), r0, '<' if i > 3 else 'v')
    # (g3,r0)='v' drops the westbound return back into the ring2 merge

    # ---- fork ----
    L.put(g(6), r2, 'Y')                     # entered heading S
    #   right copy (CW of S = W) born at (g5,r2) facing W  -> LOOPER
    #   left  copy (CCW of S = E) born at (g7,r2) facing E  -> WORKER
    L.put(g(0), r2, '^')                     # looper: glide W then up into ring1

    # ---- worker prologue on row 2 ----
    L.put(g(8), r2, 'r')                     # seq -> A
    L.put(g(9), r2, 'M')                     # B = seq
    L.put(g(10), r2, 's')                    # forward seq to the checker
    L.put(ET, r2, 'v')                       # glide E to the tree entry, turn S

    # ---- startup man: eat n, then join ring2's return lane ----
    L.put(g(8), r0, '@')
    L.put(g(9), r0, 'r')                     # discard n
    L.put(g(10), r0, 'v')
    L.put(g(10), r1, '<')                    # west; (g7,r1)='^' lifts him into the return

    # ---- montree + leaves ----
    leaves = emit_montree(L, ET, y0, lambda *a: None)
    LEAFROW = y0 + 12
    for s in range(16):
        c = leaves[s]
        L.put(c, LEAFROW, 'r')               # val -> A
        L.put(c, LEAFROW + 1, 's')           # -> lane[s]
        L.put(c, LEAFROW + 2, 'H')
    RWALL = LEAFROW + 3
    return RWALL, ET - 16, leaves


def build_fork(cy_checker=6, cx_checker=8, attach_row=20):
    L = Layout()
    CB = 21                                  # lane band west end
    ET = CB + 15                             # 36, tree entry column
    y0 = 3
    RWALL, WIN, leaves = emit_fork_reader(L, ET, y0)
    RWX = WIN - 1                            # reader west wall
    L.room(RWX, -1, (ET + 2) - RWX + 1, RWALL - (-1) + 1)
    L.input_room(RWX - 5, -1); L.pipe([(RWX - 2, 0), (RWX - 1, 0)])

    # ---- LANES ----
    TW = RWALL + 3
    for s in range(16):
        L.pipe([(leaves[s], RWALL + 1), (leaves[s], TW - 1)])

    # ---- SWEEPER (unchanged serpentine) ----
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
    hints = emit_checker_folded3(L, cx, cy, attach_j=attach_row - (cy + 1))

    # ---- PIPES ----
    seqrow = hints['seqW'][1]
    seqcol = cx - 1
    scells = [(xx, 2) for xx in range(RWX - 1, seqcol - 1, -1)] + \
             [(seqcol, r) for r in range(3, seqrow + 1)]
    place_pipe(L, scells, exit_dir=DIRS['E'])
    drow = hints['drainE'][1]
    ecol = hints['drainE'][0]
    cells = [(xx, R2) for xx in range(SWX - 1, ecol - 1, -1)] + \
            [(ecol, r) for r in range(R2 - 1, drow - 1, -1)]
    place_pipe(L, cells, exit_dir=DIRS['W'])
    outS = hints['outS']
    L.output_room(outS[0] - 1, outS[1] + 2)
    L.pipe([(outS[0], outS[1]), (outS[0], outS[1] + 1)])
    return L


if __name__ == '__main__':
    L = build_fork()
    print('FOOT', L.footprint())
    L.save(_REPO + '/solutions/tcp/tcp-fork1.man')
    print('saved tcp-fork1.man')
