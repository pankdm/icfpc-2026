#!/usr/bin/env python3
"""memory rewind v11 -- v10's engine folded from 26x26 (box 676) to 25x25 (625).

Score is max(w,h)^2 * ticks, so both extents have to come down together.  Each
is an ADDITIVE CHAIN; the win is deleting a whole link, not tidying interior
dead cells.

  WIDTH  = MEM (21) + spacer (1) + belt snake (3) + descent (1) = 26.
  HEIGHT = MEM (13) + pipe band (3) + CONTROL (8) + input overhang (2) = 26.

WIDTH -1, IN TWO PLACES THAT EACH PAY A COLUMN:
  * MEM is 21 wide but v10 left col 19 completely empty -- the 3-ring rework
    packed the rings and the fork spine into cols 12-18, so the old helper
    column is dead.  MEM_W 21 -> 20, free.
  * That alone does not shrink the box, because the right edge is set by the
    belt, not by MEM: the snake needs one empty column beside MEM's wall (a
    pipe alongside its own endpoint room's wall re-parses as a self-loop), and
    the descent column needs to clear HOP.  So HOP has to narrow too, and it
    can: ITS RATE DEPENDS ON W's PARITY.  A 2xW ring relays (W-2) pairs per
    2W-tick lap only when W-2 is EVEN; an odd run strands its last cell.
        W = 8 -> 6 pairs / 16 = 0.750   (v10)
        W = 7 -> 4 pairs / 14 = 0.571   <- narrower AND slower than MEM: fatal
        W = 6 -> 4 pairs / 12 = 0.667   <- narrower and still clear of MEM
    W=6 makes HOP 8 wide instead of 10 and keeps the belt's ceiling at 0.667
    against MEM's 0.600, an 11% margin (v6 shipped on 9%).

HEIGHT -1: THE INPUT ROOM STOPS HANGING OFF THE BOTTOM.
  The input room sat at rows 23-25 under CONTROL (16-23), so it set the last
  row.  Sliding it to 22-24 tucks it alongside CONTROL instead of below it --
  rooms may not SHARE a wall but adjacent walls in different columns are fine
  (the output room already sits like that).  Its right wall is then flush
  against CONTROL's left wall with no cell between them, so the old
  right-wall exit is gone; the command pipe now leaves through the input
  room's TOP wall, climbs col 1 through the gap between the output and input
  rooms, and turns east into CONTROL's LEFT wall.  It deliberately climbs
  before turning: going east on row 21 would run the pipe alongside its own
  input room's top wall.  CONTROL has exactly one incoming pipe, so moving
  where it attaches cannot change any `r` binding.

*** ROW 15 IS POISON, AND THAT IS THE EXPENSIVE LESSON HERE. ***
Row 15 is the attachment row for all three rooms in the lower band (output,
CONTROL and HOP all have their top wall on row 16).  A long p2 run along it
loads clean and then deadlocks every case at 5M ticks -- 0/7, including
"fresh cell reads zero", which is the tell that it breaks at STARTUP rather
than under belt pressure.  Two cheaper explanations were tested and are both
WRONG, so do not re-derive them: it is not adjacency to the command pipe
(moving the turn from col 5 to col 6 changes nothing, still 0/7), and it is
not "a pipe alongside a room wall" in general -- shipped v8 runs p2 along col
13 beside CONTROL's right wall AND along row 24 beside its bottom wall, at
24/24.  Whatever the loader does with row 15 specifically, p2 must only ever
touch it at its own attachment cell and at cols 13-14, clear of every room's
top wall.

*** THE BELT IS WHAT MAKES THIS HARD.  p2 MUST STAY > 100 CELLS. ***
The belt stores 100 memory cells in the pipes themselves, and a p2 shorter
than the standing queue lets the queue reach p2's source cell, where a
two-man HOP silently inverts order.  Shrinking the box shortens every snake
column, and the obvious route lands at 97.  Note that ROUTING CANNOT FIX
THIS BY ITSELF: every monotone path across the bottom band is the same
Manhattan length, so detours through rows 23/24 buy exactly nothing.  The
eight cells come from a region the old route never touched -- p2 climbs col
13 one row higher than before, runs WEST along row 15 (above CONTROL's top
wall, which is legal because CONTROL is not one of p2's endpoint rooms), and
only then steps up to row 14 to reach MEM.  That lands p2 at 105.

The two rows above HOP are the one place the route must NOT wander: row 15 is
alongside HOP's own top wall for cols 15-22, so p2 only ever touches it as
its attachment cell and west of col 13.
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
X_OUT, X_CMD, X_P2, X_P1 = 1, 4, 9, 16
MEM_W, MEM_H = 20, 13          # interior cols 1..18, rows 1..11
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
    for i, c in enumerate("rM`100`W%M6W/"):   # rot = 6a + r6
        P(2 + i, 3, c)
    P(15, 3, 'b')                          # BP = a  (hoisted so BOTH copies
    P(16, 3, 'v')                          #  inherit the lap count)

    # -- rows 4-6: two forks -> three men, one per ring --
    P(16, 4, 'Y')                          # fork1, parent heading south
    P(15, 4, ' '); P(14, 4, ' ')           #   right copy walks west onto MAIN
    P(17, 4, ' '); P(18, 4, 'v')           #   left copy drops and doubles back
    P(18, 5, '<'); P(17, 5, ' '); P(16, 5, 'v')
    P(16, 6, 'Y')                          # fork2, parent heading south
    vring(P, 13, 12, 4, 2)                 # MAIN: 2 relays / 10-cell lap
    vring(P, 15, 14, 6, 2); P(14, 6, 'H')  # helper 1, born west-heading on `a`
    vring_mirror(P, 17, 18, 6, 2); P(18, 6, 'H')   # helper 2, born east-heading
    P(11, 4, 'W')                          # A = r6 (B survived the relays)
    P(10, 4, 'b')                          # BP = r6
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
    # C = W puts both `Y` birth cells on ring CORNERS, which are turns rather
    # than relay cells: 5 pairs per ring -> 6, i.e. 0.625 -> 0.750 val/tick.
    # W must stay EVEN or each 2xW ring strands the last cell of an odd relay
    # run: W=6 gives 4 pairs / 12-tick lap = 0.667 val/tick in 8 columns,
    # where W=7 would be both wider and slower (0.571) than MEM's 0.600.
    hop(p, P, 15, 16, 6, 6)
    P(15 + 6, 16 + 4, 'v')                 # ring B's own corner, not hop()'s `>`

    # ================= IO =================
    p.output_room(0, 16)                   # cols 0-2, under OUT's column (x=1)
    p.input_room(0, 22)                    # cols 0-2, below CONTROL

    # ================= pipes =================
    out = [(X_OUT, PIPE_ROW), (X_OUT, PIPE_ROW + 2)]     # -> output room top
    cmd = [(X_CMD, PIPE_ROW + 2), (X_CMD, PIPE_ROW)]     # CONTROL top -> MEM
    # input room's TOP wall -> up col 1 through the room gap -> east into
    # CONTROL's LEFT wall.  Climbing first is deliberate: turning east on row
    # 21 would run the pipe alongside its own input room's top wall.
    ipipe = [(1, 21), (1, 19), (2, 19)]
    # p1 drops STRAIGHT down col 16 into HOP's top wall, which frees row 14
    # west of col 16 for p2.  X_P1 16 moves the OUT/P1 binding midpoint to
    # 8.5; every MEM `s` sits at x >= 9, and `S` sends to every outgoing pipe
    # regardless of distance, so no binding changes.
    p1 = [(X_P1, PIPE_ROW), (X_P1, 15)]                       # -> HOP top (16,16)
    # p2: HOP top (22,17) -> up col 22 -> column-snake 22/23/24/25 -> down col
    # 26 -> west row 26 (dogleg to col 6 for length) -> up col 13 -> row 15.
    # p2: HOP top (22,16) -> straight up col 22 (now two clear of MEM's wall)
    # -> snake down 23 / up 24 -> descend col 25 -> serpentine rows 24/25
    # (row 23 is alongside HOP's bottom wall and unusable) -> climb col 13.
    # snake cols 21-23 -> descent col 24 -> west along row 24 -> climb col 13
    # to row 15 -> WEST along row 15 (above CONTROL's top wall; CONTROL is not
    # a p2 endpoint, so that is legal) -> up to row 14 -> MEM.  The row-15 leg
    # is the eight cells that carry p2 from 97 back over 100.
    p2 = [(21, 15), (21, 14), (20, 14), (20, 13), (21, 13), (21, 0),
          (22, 0), (22, 14), (23, 14), (23, 0), (24, 0), (24, 24),
          (13, 24), (13, 15), (14, 15), (14, 14),
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
    out = os.path.join(os.path.dirname(__file__), 'rewind-v11.man')
    prog.save(out)
    print(out, prog.footprint())
