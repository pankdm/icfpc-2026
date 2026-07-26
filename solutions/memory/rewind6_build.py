#!/usr/bin/env python3
"""memory rewind v6 -- Track B's 2-man engine folded into a 27x27 box.

v5 = box 729, avgTicks 4922, server 14,557,218.  Track B = avgTicks 3984 at box
1764.  This is the two combined: 729 x 3984.

*** WHY THE PORT WAS BLOCKED, AND WHAT UNBLOCKS IT. ***
rewind4_build.py's header says the port fails because Track B's MEM is 22 wide,
leaving a 6-column right strip that cannot host a 10x7 HOP.  That reasoning
missed a consequence of their own engine: their rings are nrelay=4, not 8, so
the ring bottom moves from row 16 to row 11 and MEM becomes **14 tall, not 18**.
The band below MEM is then 11 rows, not 8 -- and a 7-row HOP drops straight into
it BESIDE CONTROL.  The strip is irrelevant.  Layout:

  cols  0-21 rows  0-13   MEM      (22x14: 22 wide for the helper ring at
                                    cols 18/19 + its retiring `H` at col 20)
  rows 14-15              the four lanes: OUT 1, CMD 4, P2 9, P1 14
  cols  0- 2 rows 16-18   output room        cols 3-12 rows 16-23  CONTROL
  cols 14-23 rows 17-23   HOP (Track B's hop(), W=8 -> 0.625 val/tick, which
                          must stay above MEM's 0.571 or HOP becomes the belt's
                          bottleneck and the whole tick win evaporates)
  cols  0- 2 rows 24-26   input room
  cols 22-25 rows  0-13   the belt's column-snake

*** THE BELT ROUTE IS THE HARD PART -- DO NOT "SIMPLIFY" IT. ***
Four separate constraints pin it, and every shortcut I tried violated one:
  (a) p2 must END at (9,14) via (9,15), and col 9 is inside CONTROL below row
      16, so p2's last leg runs WEST along row 15 and reaches it by climbing
      col 13 -- the only free column between CONTROL (ends 12) and HOP (14).
  (b) p1 owns (14,14) and (14,15) by force, so p2 can never cross col 14 on
      rows 14-15; it crosses underneath, on rows 24-26.
  (c) A pipe's last cell must travel INTO the room it feeds, so p1 needs two
      cells in one column above HOP's top wall -- it enters at col 15, and p2
      leaves HOP's top wall at col 22, well clear of it.
  (d) The strip snake runs by COLUMNS, not rows.  Entered at the top of col 22
      and alternating down/up, five columns would exit at the TOP; four columns
      (22,23,24,25) exit at the BOTTOM of col 25, which is where the descent to
      the band has to start.  A row-snake exits at the wrong corner and cannot
      get back down without crossing itself.
Belt length: p2 must stay > 100 cells (Track B's FIFO rule -- the standing queue
of ~100 values must not reach p2's source cell, or a multi-man HOP silently
inverts order).  The dogleg west to col 6 on row 26 exists purely to buy that
margin; without it p2 lands on 99.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from littleman import Program
# Import Track B's validated gadgets rather than re-typing them.
from rewind2_build import vring, vring_mirror, hop

# Binding: all four pipes attach on row 14, so |y-14| cancels and only columns
# decide.  CMD/P2 midpoint 6.5 -> `r` at x<=6 reads COMMANDS, x>=7 the BELT.
# OUT/P1 midpoint 7.5 -> every `s` must sit at x>=8 to reach the belt.
# The helper ring at cols 18/19 is fine: `s` is 4-5 from P1 vs 17-18 from OUT,
# `r` is 9-10 from P2 vs 14-15 from CMD.
X_OUT, X_CMD, X_P2, X_P1 = 1, 4, 9, 14
MEM_W, MEM_H = 22, 14          # interior cols 1..20, rows 1..12
PIPE_ROW = MEM_H               # attachment cells sit on row 14


def build():
    p = Program()
    P = p.put

    # ================= MEMORY : cols 0-21, rows 0-13 =================
    p.room(0, 0, MEM_W, MEM_H)

    # -- init: setup SHARES row 1 with the send run (v5's row saving) --
    for i, c in enumerate("@`20`b0"):      # cols 1-7: A=20, BP=20, A=0
        P(1 + i, 1, c)
    P(8, 1, '>')                           # loop re-entry
    for i, c in enumerate("sssss"):        # cols 9-13
        P(9 + i, 1, c)
    P(14, 1, 'v'); P(14, 2, '<')
    for x in range(10, 14):
        P(x, 2, ' ')
    P(9, 2, 'm'); P(8, 2, 'd')
    for x in range(2, 8):
        P(x, 2, ' ')
    P(1, 2, 'v')

    # -- row 3: delta -> rot -> split rot = 8a + r8 --
    P(1, 3, '>')
    for i, c in enumerate("rM`100`W%M8W/"):
        P(2 + i, 3, c)
    P(15, 3, 'b')                          # BP = a  (hoisted so BOTH copies
    P(16, 3, 'v')                          #  inherit the lap count)

    # -- row 4: the fork, then the rings, flowing WESTWARD --
    P(16, 4, 'Y')                          # south-facing parent births W and E
    P(15, 4, '<')                          # right copy (low id) = MAIN
    P(14, 4, ' ')
    P(17, 4, '>')                          # left copy (newest) = HELPER
    vring(P, 13, 12, 4, 4)                 # MAIN   ring: 4 relays / 14-cell lap
    vring_mirror(P, 18, 19, 4, 4)          # HELPER ring: identical, exits east
    P(20, 4, 'H')                          # helper retires; halted men are reaped
    P(11, 4, 'W')                          # A = r8 (B survived the relays)
    P(10, 4, 'b')                          # BP = r8
    vring(P, 9, 8, 4, 1)                   # remainder ring: 1 relay / 8-cell lap
    for x in range(5, 8):
        P(x, 4, ' ')
    P(4, 4, 'v')

    # -- tap: read the OP first, then dispatch --
    P(4, 5, 'r')                           # op        (CMD 0 vs P2 5)
    P(4, 6, 'X')                           # op=1 -> cw(south->west); 0 -> south
    # READ arm: cannot use rows 5-8, ring1 owns cols 8/9 there.
    P(4, 7, ' '); P(4, 8, ' ')
    P(4, 9, '>'); P(5, 9, ' '); P(6, 9, ' ')
    P(7, 9, 'r')                           # belt value   (P2 2 vs CMD 3)
    P(8, 9, 'S')                           # -> output pipe AND belt (reinject)
    P(9, 9, ' '); P(10, 9, ' '); P(11, 9, 'v')
    P(11, 10, ' '); P(11, 11, ' '); P(11, 12, '<')
    # WRITE arm
    P(3, 6, 'v')
    for y in range(7, 10):
        P(3, y, ' ')
    P(3, 10, '>')
    P(4, 10, 'r')                          # new value    (CMD 0 vs P2 5)
    P(5, 10, 'M')                          # B = value
    P(6, 10, ' ')
    P(7, 10, 'r')                          # old value, discarded (P2 2 vs CMD 3)
    P(8, 10, 'W')                          # A = value
    P(9, 10, 's')                          # -> belt      (P1 5 vs OUT 8)
    P(10, 10, 'v'); P(10, 11, ' '); P(10, 12, '<')
    # -- return: WEST along row 12, then north up the free col 1 into row 3 --
    for x in range(2, 10):
        P(x, 12, ' ')
    P(1, 12, '^')
    for y in range(4, 12):
        P(1, y, ' ')

    # ================= CONTROL : 10x8, cols 3-12, rows 16-23 =================
    CX, CY = 3, 17
    C = lambda x, y, c: P(CX + x, CY + y, c)
    p.room(CX, CY, 10, 8)
    for i, c in enumerate(">@rbr-sv"):     # loop turn, @, op, BP=op, addr,
        C(1 + i, 1, c)                     #   delta, send delta, south
    C(8, 2, '+')                           # A = delta + prev = addr
    C(8, 3, 'M')                           # B = addr
    C(8, 4, 'd')                           # op>0 -> cw(south->west) = WRITE
    C(7, 4, '1'); C(6, 4, 's')             # send op = 1
    C(5, 4, 'r'); C(4, 4, 's')             # read the value, send it
    C(3, 4, 'v'); C(3, 5, ' '); C(3, 6, '<')
    C(8, 5, '0'); C(8, 6, '<')
    C(7, 6, 's')                           # send op = 0 (no value follows)
    for x in (6, 5, 4, 2):
        C(x, 6, ' ')
    C(1, 6, '^')
    C(1, 5, '1'); C(1, 4, '+'); C(1, 3, 'M'); C(1, 2, ' ')
    for y in (2, 3, 5):
        C(2, y, ' ')
    for x in (4, 5, 6, 7):
        C(x, 2, ' '); C(x, 3, ' '); C(x, 5, ' ')
    C(3, 2, ' '); C(3, 3, ' ')

    # ================= HOP : cols 14-23, rows 17-23, TWO men ============
    # W=8 -> two rings of 5 pairs per 16-tick lap = 0.625 val/tick, safely
    # above MEM's 0.571 so MEM stays the bottleneck (which is what keeps MEM's
    # two men from ever blocking on either side).
    hop(p, P, 15, 17, 8, 5)

    # ================= IO =================
    p.output_room(0, 17)                   # cols 0-2, under OUT's column (x=1)
    p.input_room(0, 24)                    # cols 0-2, below CONTROL

    # ================= pipes =================
    out = [(X_OUT, PIPE_ROW), (X_OUT, PIPE_ROW + 2)]     # -> output room top
    cmd = [(X_CMD, PIPE_ROW + 2), (X_CMD, PIPE_ROW)]     # CONTROL top -> MEM
    ipipe = [(3, 25), (5, 25), (5, 26), (8, 26), (8, 25)]    # input room right wall -> CONTROL bottom
    p1 = [(X_P1, PIPE_ROW), (X_P1, 15), (16, 15), (16, 16)]   # -> HOP top (16,17)
    # p2: HOP top (22,17) -> up col 22 -> column-snake 22/23/24/25 -> down col
    # 26 -> west row 26 (dogleg to col 6 for length) -> up col 13 -> row 15.
    p2 = [(22, 16), (22, 14), (23, 14), (23, 0), (24, 0), (24, 13),
          (25, 13), (25, 0), (26, 0), (26, 26), (13, 26), (13, 15),
          (X_P2, 15), (X_P2, PIPE_ROW)]
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
    out = os.path.join(os.path.dirname(__file__), 'rewind-v6.man')
    prog.save(out)
    print(out, prog.footprint())
