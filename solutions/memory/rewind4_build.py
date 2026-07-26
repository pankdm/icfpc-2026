#!/usr/bin/env python3
"""memory rewind v4 -- the 28x28 fold.  box 784, avgTicks 4923, local 3.86M.

*** THE FLOORPLAN, AND THE ONE RULE THAT DETERMINES IT. ***
A pipe is AT LEAST TWO CELLS LONG, so every pipe hanging off MEM's bottom wall
costs BOTH row 18 and row 19 in its own column.  Rows 18-19 are therefore
blocked at cols 1, 4, 9, 14 and NOTHING can run horizontally across them.
Everything else follows:

  cols  0-16 rows  0-17   MEM            (17x18, unchanged from v3)
  cols  0- 2 rows 20-22   output room    (straight down the OUT lane, col 1)
  cols  3-12 rows 20-27   CONTROL        (straight down the CMD lane, col 4)
  cols 15-17 rows 24-26   input room     -> ipipe (14,25),(13,25) -> CONTROL
  cols 17-27 rows  0- 3   HOP            (top of the right strip)
  cols 18-27 rows  4-21   the belt

CONTROL is 8 rows tall (20-27) and 10 wide; it is an IMPASSABLE WALL for rows
20-27 across cols 3-12, so both west lanes must reach it/the output room
vertically, and the belt must stay east of col 13.  The belt's return is the
delicate part -- p1 owns (14,18) and (14,19) by force, so p2 CANNOT come back
along row 19 from the east.  Instead:

  p1: (14,18) -> (14,19) -> east row 19 to col 17 -> north col 18 -> HOP (18,3)
  p2: HOP (25,3) -> boustrophedon cols 19-27 rows 5-12 -> south col 19 to row
      21 -> WEST along row 21 across col 14 -> north col 13 -> WEST along row
      19 (cols 13..9, all west of p1's col 14) -> (9,18)

so the two halves of the belt interleave without ever crossing.  Belt = 110
cells (p1 21 + p2 89) for 100 values; see the 2-man pump note at the bottom.

ATTACHMENT COLUMNS MOVED: OUT 3->1 and CMD 1->4, so that the output room can
sit west of CONTROL instead of underneath it.  Re-derived binding (all four
pipes attach on row 18, so the |y-18| term cancels and only columns matter):
    CMD/P2 midpoint 6.5 : `r` at x<=6 reads COMMANDS, at x>=7 reads the BELT
    OUT/P1 midpoint 7.5 : every `s` must sit at x>=8 to reach the belt
The write arm's belt read moved 6 -> 7 for this (col 6 binds CMD now).

--- protocol, introduced in v3 and unchanged here -------------------------
PROTOCOL: op before value, no value on reads.

Read rewind2_build.py's docstring first; everything there about pipe binding,
the vertical rings and the box arithmetic still holds.  This file changes only
the CONTROL <-> MEMORY wire protocol and re-lays CONTROL accordingly.

OLD wire (v2):  delta, value, op          (reads sent a dummy value 0)
NEW wire (v3):  delta, op [, value]       (value only on writes)

  CONTROL  main : r(op) b r(addr) -(delta) s(delta) +(addr) M(B=addr) d
           write: 1 s(op=1) r(value) s(value)
           read : 0 s(op=0)
           merge: 1 + M          -- prev := addr+1, run by BOTH arms
  MEM tap  : r(op) X
           read arm : r(belt) S            (S = send to every outgoing pipe,
                                            i.e. output AND belt reinject)
           write arm: r(value) M r(belt) W s(belt)

Two wins:
  * a READ now moves 2 values instead of 3 -- one fewer send in CONTROL and one
    fewer read in MEM, so ticks DROP.
  * CONTROL's arms shrink from 8 ops to 6, and moving the prev-update ('1','+',
    'M') onto the MERGED tail (both arms leave B=addr, so it works unchanged for
    either) cuts the pre-branch main line to 8 ops.  CONTROL is now 8 ROWS tall
    instead of 9, which is the row the 28x28 fold needs:
        MEM 18 + cmd 2 + CONTROL 8 = 28.

CONTROL interior (cols 1-8, rows 1-6 of a 10x8 room):

      1 2 3 4 5 6 7 8
    1 > @ r b r - s v
    2               +
    3 M             M
    4 + v s r s 1 - d      (row 4 read WESTWARD: 1 s r s then 'v')
    5 1   .         0
    6 ^ . < . . . s <      (row 6 read WESTWARD from the '<' at col 8)

The write arm turns south at (3,4) and rejoins the read arm's row-6 run at
(3,6); col 1 rows 3-5 is the shared tail.  Both arms reach (1,1) with B=addr.

MEM's tap is 2 cells shorter, but MEM's height is set by ring8 (top=5,
nrelay=8 -> bot=16), not by the tap, so MEM stays 17x18.  The read arm still
has to run along row 10: rows 6-9 of cols 8/9 belong to ring1 and row 8 in
particular carries ring1's 's' at (9,8).

STATUS: see the commit message.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools'))
from littleman import Program

# MEMORY bottom-wall pipe attachment columns -- unchanged from v2, and the
# reason every instruction below sits in the column it does.  All four pipes
# attach on the same row, so the |y - 18| term cancels and binding is decided
# purely by column:
#     CMD/P2 midpoint 6.5 : `r` at x<=6 reads COMMANDS, at x>=7 reads the BELT
#     OUT/P1 midpoint 7.5 : every `s` must sit at x>=8 to reach the belt
X_OUT, X_CMD, X_P2, X_P1 = 1, 4, 9, 14
MEM_W, MEM_H = 17, 18          # room(0,0,MEM_W,MEM_H) -> interior 1..15 x 1..16
PIPE_ROW = MEM_H               # attachment cells sit on row 18


def vring(P, down, up, top, nrelay):
    """Vertical 2-column ring with a MERGED guard-bypass / ring-exit cell.

    The man arrives WESTBOUND on row `top`.  `down` is the southbound column,
    `up` (== down-1) the northbound one.  Returns the bottom row used.
    See rewind2_build.py for the full derivation.
    """
    dn = 2 * ((nrelay + 1) // 2)       # relay cells on the southbound column
    upn = 2 * nrelay - dn              # relay cells on the northbound column
    m_on_up = (dn - upn) >= 1
    bot = top + (2 if m_on_up else 3) + dn
    P(down, top, 'a')                  # guard (test BEFORE entering)
    P(down, top + 1, 'v')              # entry + loop-back turn target
    off = top + 2
    if not m_on_up:
        P(down, top + 2, 'm')          # BP-- once per lap
        off = top + 3
    for i in range(dn):                # southbound relays: r s r s ...
        P(down, off + i, 'rs'[i % 2])
    P(down, bot, '<')
    P(up, bot, '^')
    for i in range(upn):               # northbound relays, in travel order
        P(up, bot - 1 - i, 'rs'[i % 2])
    for y in range(top + 2, bot - upn):
        P(up, y, ' ')
    if m_on_up:
        P(up, top + 2, 'm')            # BP-- once per lap (spare up-column cell)
    P(up, top + 1, 'd')                # BP>0 -> cw(north->east) back to entry
    P(up, top, '<')                    # merged exit / bypass
    return bot


def build():
    p = Program()
    P = p.put

    # ================= MEMORY : cols 0-16, rows 0-17 =================
    p.room(0, 0, MEM_W, MEM_H)

    # -- init: A=20, BP=20, A=0, then 20 laps x 5 sends of 0 = 100 zeros --
    # 5 sends/lap keeps every init 's' at x>=9 (the OUT/P1 midpoint is 7.5).
    for i, c in enumerate("@`20`b0v"):
        P(1 + i, 1, c)
    P(8, 2, '>')
    for i, c in enumerate("sssss"):        # cols 9-13
        P(9 + i, 2, c)
    P(14, 2, 'v'); P(14, 3, '<')
    for x in range(10, 14):
        P(x, 3, ' ')
    P(9, 3, 'm'); P(8, 3, 'd')
    for x in range(2, 8):                  # BP==0 -> west, then down into row 4
        P(x, 3, ' ')
    P(1, 3, 'v')

    # -- row 4: delta -> rot -> split rot = 8a + r8 --
    P(1, 4, '>')
    for i, c in enumerate("rM`100`W%M8W/"):
        P(2 + i, 4, c)
    P(15, 4, 'v')

    # -- row 5: the two rings, flowing WESTWARD --
    P(15, 5, '<')
    P(14, 5, 'b')                          # BP = a
    vring(P, 13, 12, 5, 8)                 # main ring: 8 relays / 22-cell lap
    P(11, 5, 'W')                          # A = r8 (B survived the relays)
    P(10, 5, 'b')                          # BP = r8
    vring(P, 9, 8, 5, 1)                   # remainder ring: 1 relay / 8-cell lap
    for x in range(5, 8):
        P(x, 5, ' ')
    P(4, 5, 'v')

    # -- tap: read the OP first, then dispatch --
    P(4, 6, 'r')                           # op        (CMD 0 vs P2 5)
    P(4, 7, 'X')                           # op=1 -> cw(south->west); op=0 -> south
    # READ arm (op == 0): tap the belt, output AND reinject.  It cannot use
    # rows 6-9: ring1 owns cols 8/9 there, and (9,8) is its 's'.
    P(4, 8, ' '); P(4, 9, ' ')
    P(4, 10, '>'); P(5, 10, ' '); P(6, 10, ' ')
    P(7, 10, 'r')                          # belt value   (P2 2 vs CMD 3)
    P(8, 10, 'S')                          # -> output pipe AND belt (reinject)
    P(9, 10, ' '); P(10, 10, ' '); P(11, 10, 'v')
    for y in range(11, 16):
        P(11, y, ' ')
    P(11, 16, '<')
    # WRITE arm (op == 1): read the new value, discard the old belt cell, send.
    P(3, 7, 'v')
    for y in range(8, 14):
        P(3, y, ' ')
    P(3, 14, '>')
    P(4, 14, 'r')                          # new value    (CMD 0 vs P2 5)
    P(5, 14, 'M')                          # B = value
    P(6, 14, ' ')                          # col 6 would tie-ish: CMD 2 vs P2 3
    P(7, 14, 'r')                          # old value, discarded (P2 2 vs CMD 3)
    P(8, 14, 'W')                          # A = value
    P(9, 14, 's')                          # -> belt      (P1 5 vs OUT 8)
    P(10, 14, 'v'); P(10, 15, ' '); P(10, 16, '<')
    # -- return: WEST along row 16, then north up the free col 1 into row 4 --
    for x in range(2, 10):
        P(x, 16, ' ')
    P(1, 16, '^')
    for y in range(5, 16):
        P(1, y, ' ')

    # ================= CONTROL : 10x8, cols 3-12, rows 20-27 =================
    CX, CY = 3, 20
    C = lambda x, y, c: P(CX + x, CY + y, c)
    p.room(CX, CY, 10, 8)
    for i, c in enumerate(">@rbr-sv"):     # loop turn, @, op, BP=op, addr,
        C(1 + i, 1, c)                     #   delta, send delta, south
    C(8, 2, '+')                           # A = delta + prev = addr
    C(8, 3, 'M')                           # B = addr
    C(8, 4, 'd')                           # op>0 -> cw(south->west) = WRITE
    # WRITE arm, westward along row 4
    C(7, 4, '1'); C(6, 4, 's')             # send op = 1
    C(5, 4, 'r'); C(4, 4, 's')             # read the value, send it
    C(3, 4, 'v'); C(3, 5, ' '); C(3, 6, '<')   # drop onto the shared row-6 tail
    # READ arm, straight south then west along row 6
    C(8, 5, '0'); C(8, 6, '<')
    C(7, 6, 's')                           # send op = 0 (no value follows)
    for x in (6, 5, 4, 2):
        C(x, 6, ' ')
    C(1, 6, '^')
    # MERGED tail: both arms arrive with B = addr, so prev := addr + 1 here.
    C(1, 5, '1'); C(1, 4, '+'); C(1, 3, 'M'); C(1, 2, ' ')
    for y in (2, 3, 5):
        C(2, y, ' ')
    for x in (4, 5, 6, 7):
        C(x, 2, ' '); C(x, 3, ' '); C(x, 5, ' ')
    C(3, 2, ' '); C(3, 3, ' ')

    # ================= HOP : cols 17-27, rows 0-3 (top of the right strip) ====
    # Interior is 9 wide (cols 18-26), one column narrower than v3's, because
    # col 16 belongs to MEM.  6 relay pairs per 18-cell lap = 3.0 ticks/value,
    # against ring8's 2.75 -- HOP is the belt's slowest stage, so if ticks
    # regress this room is the first place to look.
    HX, HY = 17, 0
    H = lambda x, y, c: P(HX + x, HY + y, c)
    p.room(HX, HY, 11, 4)
    H(1, 1, '>'); H(2, 1, '@')
    for i, c in enumerate("rsrsrs"):       # cols 20-25
        H(3 + i, 1, c)
    H(9, 1, 'v'); H(9, 2, '<')
    for i, c in enumerate("rsrsrs"):       # cols 25-20, travelling west
        H(8 - i, 2, c)
    H(2, 2, ' '); H(1, 2, '^')

    # ================= IO =================
    p.output_room(0, 20)                   # cols 0-2, under OUT's column (x=1)
    p.input_room(15, 24)                   # cols 15-17, east of CONTROL

    # ================= pipes =================
    # Every lane costs BOTH row 18 and row 19 (a pipe is at least two cells
    # long), so rows 18-19 are blocked at cols 1, 4, 9 and 14 and no wire can
    # run horizontally across them.  That is what fixes the floorplan:
    #   * CONTROL and the output room sit WEST (cols 0-12), reached straight
    #     down their own lanes;
    #   * the belt lives EAST, and p2 comes back to (9,19) along row 19 WEST of
    #     p1's mandatory (14,19), after crossing col 14 down at row 21.
    # p1 and p2 therefore never cross: p1 = col 14 + row 19 cols 14-17 + col 18,
    # p2 = cols 19-27 + row 21 cols 13-19 + col 13 + row 19 cols 9-13.
    out = [(X_OUT, PIPE_ROW), (X_OUT, PIPE_ROW + 1)]        # -> output room top
    cmd = [(X_CMD, PIPE_ROW + 1), (X_CMD, PIPE_ROW)]        # CONTROL top -> MEM
    ipipe = [(14, 25), (13, 25)]           # input room left wall -> CONTROL col 12
    p1 = [(X_P1, PIPE_ROW), (X_P1, 19), (18, 19), (18, 4)]  # -> HOP bottom (18,3)
    # p2: HOP bottom (25,3) -> boustrophedon over cols 19-27, rows 5-12 -> out
    # at col 19 -> west along row 21 -> col 13 -> row 19 -> (9,18).
    p2 = [(25, 4), (25, 5), (27, 5), (27, 6), (19, 6)]
    for i, y in enumerate(range(7, 13)):   # rows 7..12 alternate E / W
        p2 += [(19, y), (27, y)] if i % 2 == 0 else [(27, y), (19, y)]
    p2 += [(19, 21), (13, 21), (13, 19), (X_P2, 19), (X_P2, PIPE_ROW)]
    for pts in (out, cmd, ipipe, p1, p2):
        p.pipe(pts)
    print(f"# P1={pipelen(p1)} P2={pipelen(p2)} total={pipelen(p1)+pipelen(p2)}",
          file=sys.stderr)
    return p


def pipelen(pts):
    n = 1
    for i in range(len(pts) - 1):
        n += abs(pts[i + 1][0] - pts[i][0]) + abs(pts[i + 1][1] - pts[i][1])
    return n


if __name__ == '__main__':
    prog = build()
    out = os.path.join(os.path.dirname(__file__), 'rewind-v4.man')
    prog.save(out)
    print(out, prog.footprint())
