#!/usr/bin/env python3
"""memory rewind v8 -- v6's engine, folded from 27x27 (box 729) to 26x26 (676).

v6 = MEM 22x14 over cols 0-21/rows 0-13, everything else below it, and the
belt's column-snake in cols 23-26.  Two independent cells of slack were left:

  HEIGHT.  MEM's return corridor sat on row 12 while row 11 was empty across
  cols 1-11 (the ring bottoms are at cols 12/13 and 18/19).  Dropping the
  return to row 11 makes MEM 13 tall, and every room below it moves up one:
  CONTROL 16-23, HOP 16-22, output 16-18, input 23-25 -> 26 rows total.
  PIPE_ROW goes 14 -> 13, so every pipe attachment moves with it; the four
  lanes still share one row, so the |y - PIPE_ROW| term still cancels out of
  every r/s binding decision and no midpoint tie changes.

  WIDTH.  The helper ring's merged exit/bypass cell at (19,4) was `>` feeding
  a dedicated `H` at (20,4).  Both the ring exit and the BP==0 bypass want to
  retire, so the cell can simply BE the `H` -- MEM loses col 20 and is 21
  wide.  That is what buys the width: the belt's first snake column had to
  keep one empty column between itself and MEM's right wall (a pipe alongside
  its own endpoint room's wall re-parses as a self-loop), so a narrower MEM
  slides the whole snake one column left, cols 22-25 instead of 23-26.

BELT LENGTH IS THE CONSTRAINT THAT PAYS FOR THE FOLD.  Shrinking the box
shortens every snake column, and p2 must stay > 100 cells or the standing
queue of ~100 values reaches p2's source cell and a multi-man HOP silently
inverts order.  The naive folded route lands at 96.  The length is bought
back in the band BELOW HOP: rows 24-25 are two clear rows (row 23 is
off-limits, being alongside HOP's own bottom wall), and p2 serpentines west
along row 24 and back east along row 25 before climbing col 13.  The builder
prints P1/P2 on every run -- if P2 <= 100 the fold is not safe, whatever the
grader says on public cases.
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
MEM_W, MEM_H = 21, 13          # interior cols 1..19, rows 1..11
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
    P(19, 4, 'H')                          # the merged exit/bypass cell IS the
                                           # retirement: both arrivals halt, and
                                           # MEM loses col 20 entirely
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
    P(11, 10, ' '); P(11, 11, '<')
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
    P(10, 10, 'v'); P(10, 11, '<')
    # -- return: WEST along row 11, then north up the free col 1 into row 3 --
    for x in range(2, 10):
        P(x, 11, ' ')
    P(1, 11, '^')
    for y in range(4, 11):
        P(1, y, ' ')

    # ================= CONTROL : 10x8, cols 3-12, rows 16-23 =================
    CX, CY = 3, 16
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
    hop(p, P, 15, 16, 8, 5)

    # ================= IO =================
    p.output_room(0, 16)                   # cols 0-2, under OUT's column (x=1)
    p.input_room(0, 23)                    # cols 0-2, below CONTROL

    # ================= pipes =================
    out = [(X_OUT, PIPE_ROW), (X_OUT, PIPE_ROW + 2)]     # -> output room top
    cmd = [(X_CMD, PIPE_ROW + 2), (X_CMD, PIPE_ROW)]     # CONTROL top -> MEM
    ipipe = [(3, 24), (5, 24), (5, 25), (8, 25), (8, 24)]    # input room right wall -> CONTROL bottom
    p1 = [(X_P1, PIPE_ROW), (X_P1, 14), (16, 14), (16, 15)]   # -> HOP top (16,16)
    # p2: HOP top (22,17) -> up col 22 -> column-snake 22/23/24/25 -> down col
    # 26 -> west row 26 (dogleg to col 6 for length) -> up col 13 -> row 15.
    # p2: HOP top (22,16) -> straight up col 22 (now two clear of MEM's wall)
    # -> snake down 23 / up 24 -> descend col 25 -> serpentine rows 24/25
    # (row 23 is alongside HOP's bottom wall and unusable) -> climb col 13.
    p2 = [(22, 15), (22, 0), (23, 0), (23, 13), (24, 13), (24, 0),
          (25, 0), (25, 25), (9, 25), (9, 24), (13, 24), (13, 14),
          (X_P2, 14), (X_P2, PIPE_ROW)]
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
    out = os.path.join(os.path.dirname(__file__), 'rewind-v8.man')
    prog.save(out)
    print(out, prog.footprint())
