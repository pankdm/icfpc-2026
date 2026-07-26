#!/usr/bin/env python3
"""memory rewind v12 -- v11's engine folded from 25x25 (box 625) to 24x24 (576).

MEM, the rings, the fork spine, CONTROL and HOP are all bit-identical to v11.
Only the belt and the two I/O rooms move.  Two assumptions v11 froze turned
out to be free variables, and both were measured rather than argued:

*** 1. THE BELT CLIFF IS p2 >= 99, AND IT IS ABOUT p2 ALONE. ***
v11 shipped p2 = 101 on the belief that "p2 > 100".  Bisected properly:
    p1=3, p2= 97, L=100  ->  2/7   (diverges on every write case)
    p1=3, p2= 99, L=102  ->  7/7 and 89/89 fuzz
    p1=5, p2= 97, L=102  ->  2/7   <- the decisive one
The third measurement is why p1 is irrelevant: holding p2 at 97 and spending
two extra cells on p1 does NOT rescue it, so the constraint is the length of
p2 by itself, not the total capacity of the loop.  The belt's standing queue
of 100 values has to fit in p2 without reaching p2's source cell, and no
amount of p1 helps.  Budget accordingly: p2 >= 99, and p1 may be as short as
geometry likes.

*** 2. THE SNAKE DOES NOT NEED A SPACER COLUMN BESIDE MEM'S WALL. ***
Every build since v6 left one empty column between MEM's right wall and the
belt's first snake column, on the theory that a pipe alongside its own
endpoint room's wall re-parses as a self-loop.  That is not true here: the
snake's first column now runs directly against MEM's right wall.  This is the
whole width win, and it is what makes 24 wide reachable WITHOUT touching MEM
-- the alternative was freeing MEM's col 18, which forces the ring block to
cols 11-17, the fork spine onto col 15, and collides with row 3 (the rot
expression fills cols 2-14 and the BP-setting `b` can then only take col 15,
exactly where the spine must turn south).  None of that is needed.

    WIDTH  = MEM 20 + snake 3 + descent 1 = 24   (was + 1 spacer)
    HEIGHT = MEM 13 + band 3 + CONTROL 8 = 24    (input room no longer hangs)

HEIGHT -1: the input room goes flush.  v11 had it at rows 22-24 against
CONTROL's 16-23, still overhanging by one row.  At rows 21-23 its bottom wall
lands on CONTROL's, so CONTROL sets the last row and nothing hangs below it.
Its command pipe keeps v11's shape -- out through the TOP wall, up col 1
through the gap between the output and input rooms, then east into CONTROL's
LEFT wall -- just one row higher.

*** WHERE p2's CELLS COME FROM NOW. ***
Losing a row costs the descent and the bottom leg a cell each, so the naive
route lands at 84.  The cells come from a region every previous version wasted:
cols 13 and 14 between CONTROL and HOP are BOTH free for their whole height,
so p2 climbs them as a full serpentine (18 cells over rows 15-23) instead of
running up one of them and leaving the other empty.  That is worth +8 over the
straight climb, because a serpentine is the one shape that beats the Manhattan
bound -- every monotone path across a band is the same length, which is why
v11's attempts to buy cells by detouring through the bottom band all bought
exactly zero.  p2 = 101.

Row 15 is still poison for anything but attachment cells: it is the
attachment row for the output room, CONTROL and HOP alike (all three have
their top wall on row 16), and a long p2 run along it deadlocks at load.  Cols
13-14 are the exception -- they sit between CONTROL and HOP, above no room at
all.
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
MEM_W, MEM_H = 19, 13          # interior cols 1..17, rows 1..11
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
    # The whole block sits one column west of v11 so MEM can be 19 wide, which
    # is what the belt needs: its snake requires an empty spacer column beside
    # MEM's right wall (running flush against it is an explicit load error,
    # "pipe loops back to the room it started from").  The spine is the piece
    # that had to be re-placed, and it is placed by two facts:
    #   * `b` can only sit at col 15 -- row 3's rot expression fills cols 2-14
    #     and BP must be set after the divide -- so the spine turns south at
    #     col 16, one east of it.
    #   * fork1's east copy would be born into MEM's wall if the fork sat at
    #     col 17, so fork1 stays at col 16 and the east copy is walked DOWN
    #     col 17 and back west along row 5 to fork2 on col 15.
    # Both helper rings top at row 6, so rows 3-5 of their columns are free and
    # the spine borrows them; that is what fits 3 rings + spine in 7 columns.
    P(16, 4, 'Y')                          # fork1, parent heading south
    P(15, 4, ' '); P(14, 4, ' '); P(13, 4, ' ')   # right copy walks west
    P(17, 4, 'v')                          # left copy drops down col 17 ...
    P(17, 5, '<'); P(16, 5, ' '); P(15, 5, 'v')   # ... and back west to fork2
    P(15, 6, 'Y')                          # fork2: births BOTH helper guards
    vring(P, 12, 11, 4, 2)                 # MAIN: 2 relays / 10-cell lap
    vring(P, 14, 13, 6, 2); P(13, 6, 'H')  # helper 1, born west-heading on `a`
    vring_mirror(P, 16, 17, 6, 2); P(17, 6, 'H')  # helper 2, born east-heading
    P(10, 4, 'W')                          # A = r6 (B survived the relays)
    P(9, 4, 'b')                           # BP = r6
    # The remainder ring cannot go further west than cols 7/8: its `s` lands on
    # the down column, and the OUT/P1 midpoint (7.5 at X_P1=14) needs x >= 8.
    vring(P, 8, 7, 4, 1)                   # remainder ring: 1 relay / 8-cell lap
    for x in range(5, 7):
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
    P(9, 9, ' '); P(10, 9, 'v')            # MAIN's return column is 11 now, so
                                           # the read arm drops on col 10 and
                                           # SHARES the write arm's turn cell:
                                           # a `v` is a no-op for a man already
                                           # heading south.
    P(10, 11, '<')
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
    P(10, 10, 'v')
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
    p.input_room(0, 21)                    # cols 0-2, below CONTROL

    # ================= pipes =================
    out = [(X_OUT, PIPE_ROW), (X_OUT, PIPE_ROW + 2)]     # -> output room top
    cmd = [(X_CMD, PIPE_ROW + 2), (X_CMD, PIPE_ROW)]     # CONTROL top -> MEM
    # input room's TOP wall -> up col 1 through the room gap -> east into
    # CONTROL's LEFT wall.  Climbing first is deliberate: turning east on row
    # 21 would run the pipe alongside its own input room's top wall.
    ipipe = [(1, 20), (1, 19), (2, 19)]
    # p1 drops STRAIGHT down col 16 into HOP's top wall, which frees row 14
    # west of col 16 for p2.  X_P1 16 moves the OUT/P1 binding midpoint to
    # 8.5; every MEM `s` sits at x >= 9, and `S` sends to every outgoing pipe
    # regardless of distance, so no binding changes.
    p1 = [(X_P1, PIPE_ROW), (X_P1, 14), (16, 14), (16, 15)]   # -> HOP top (16,16)
    # p2: HOP top (22,17) -> up col 22 -> column-snake 22/23/24/25 -> down col
    # 26 -> west row 26 (dogleg to col 6 for length) -> up col 13 -> row 15.
    # p2: HOP top (22,16) -> straight up col 22 (now two clear of MEM's wall)
    # -> snake down 23 / up 24 -> descend col 25 -> serpentine rows 24/25
    # (row 23 is alongside HOP's bottom wall and unusable) -> climb col 13.
    # snake cols 21-23 -> descent col 24 -> west along row 24 -> climb col 13
    # to row 15 -> WEST along row 15 (above CONTROL's top wall; CONTROL is not
    # a p2 endpoint, so that is legal) -> up to row 14 -> MEM.  The row-15 leg
    # is the eight cells that carry p2 from 97 back over 100.
    # snake cols 20-22 (col 20 runs flush against MEM's right wall), descent
    # col 23, then a full serpentine up cols 13/14 -- the one shape that beats
    # the Manhattan bound and the reason p2 clears 99 in a 24-wide box.
    p2 = [(21, 15), (21, 14), (20, 14), (19, 14), (19, 13), (20, 13),
          (20, 0), (21, 0), (21, 13),
          (22, 13), (22, 0), (23, 0), (23, 23),
          (14, 23),
          (13, 23),
          (13, 22),
          (14, 22),
          (14, 21),
          (13, 21),
          (13, 20),
          (14, 20),
          (14, 19),
          (13, 19),
          (13, 18),
          (14, 18),
          (14, 17),
          (13, 17),
          (13, 16),
          (14, 16),
          (14, 15),
          (13, 15),
          (13, 14), (X_P2, 14), (X_P2, PIPE_ROW)]
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
    out = os.path.join(os.path.dirname(__file__), 'rewind-v13.man')
    prog.save(out)
    print(out, prog.footprint())
