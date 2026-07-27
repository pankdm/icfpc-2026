#!/usr/bin/env python3
"""memory rewind v14 -- v13 with CONTROL folded 10x8 -> 10x7.  Box UNCHANGED at
576; this is a validated COMPONENT fold, banked for a future architecture, not
a score win.  7/7 public, 89/89 fuzz, avgTicks identical to v13 (3588.9).

*** THE FOLD. ***
Six interior rows were forced by CONTROL's RIGHT arm, which ran `+ M d 0 <`
below the main line: the read branch spent one row loading A=0 and another
turning west.  Both jobs move onto the westward run -- the branch turns west
immediately at (8,5) and loads `0` at (7,5) -- so the arm is `+ M d <` and five
interior rows suffice.  The write branch then rejoins on the SAME row at
(3,5)=`<`, a cell that turns the write man arriving from the north and is a
no-op for the read man already heading west.  That sharing is safe because a
room holds at most one `@` and this one never forks: the two branches are the
same man at different times.  The left arm loses its blank and becomes
`^ 1 + M` over rows 5..2.

*** WHY THIS DOES NOT GIVE 23x23, WHICH WAS THE POINT OF DOING IT. ***
The freed row makes the height chain add to 23 (MEM 13 + band 3 + rooms 7), so
on paper 23x23 follows.  It does not, and the reason is the BELT, not the
height:

p2 must be >= 99 cells (measured) AND must deliver to MEM's WEST side -- the
remainder ring's `r` and the tap's belt reads sit at cols 7-8, and they only
bind P2 rather than CMD if P2 attaches west of centre.  So p2 has to gather ~99
cells in the top-right block and then cross the ISTHMUS between CONTROL (ends
col 12) and HOP (starts col 15) to reach it.  That isthmus is two columns wide,
and p1 must cross it too.

In a 24-tall grid p2 crosses BELOW HOP: HOP is 7 tall at rows 16-22 while the
grid runs to row 23, so row 23 is a free westward corridor, and p2 reaches it
via the full-height descent column east of HOP.  Fold CONTROL and the grid ends
at row 22 -- HOP's own bottom wall -- so both of those disappear at once:
  * no row below HOP, so no westward corridor;
  * the descent column can still run, but it dead-ends at row 22 because rows
    16-22 of every column from 15 east are HOP, and row 15 is poison (it is the
    attachment row for output, CONTROL and HOP alike -- measured 0/7).
That leaves row 14 as the only crossing, and p1 needs it: p1 must reach HOP's
top wall, whose non-corner cells start at col 16, so from X_P1 <= 14 it runs
east along row 14 and blocks the isthmus.  Pushing X_P1 to 17 for a clean
one-column drop breaks binding instead -- the OUT/P1 midpoint goes to 9 and the
remainder ring's `s` at x=8 binds the output pipe.

Measured p2 ceiling in every 23-tall arrangement tried: no connected route at
all to MEM's west side, and at most ~86 cells even ignoring delivery.  Moving
HOP east to widen the isthmus to three columns does not help: the descent then
has no column east of HOP inside 24, and p1 still consumes a crossing.

So 23x23 needs one of: a shorter rot expression (row 3's 13 cells set MEM's
width, and the 12-cell reordering `100`/M/r/% puts the delta read at col 8
where it binds P2 instead of CMD), a remainder ring relocated east of the
counted rings so cols 7-8 stop needing P2 (order of relays is free -- only the
COUNT matters -- but the man would have to backtrack), or a HOP that is 6 rows
tall.
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
    p.room(CX, CY, 10, 7)                  # 10x7, was 10x8 -- see fold below
    # *** CONTROL FOLDED 8 -> 7 TALL. ***
    # Six interior rows were forced by the RIGHT arm: below the main line it ran
    # `+ M d 0 <`, five cells, because the read branch spent one row loading
    # A=0 and another turning west.  Those two jobs move onto the westward run:
    # the branch turns west immediately at (8,5) and loads `0` at (7,5), so the
    # arm is `+ M d <` and five interior rows suffice.
    # The write branch then rejoins on the SAME row, at (3,5)=`<` -- that cell
    # turns the write man arriving from the north AND is a no-op for the read
    # man already heading west.  Safe because a room holds at most one `@` and
    # this one never forks, so the two branches are the same man at different
    # times and can share cells freely.
    # The left arm loses its blank at (1,2) and becomes `^ 1 + M` over rows
    # 5..2, reaching (1,1)=`>` exactly as before.
    for i, c in enumerate(">@rbr-sv"):     # loop turn, @, op, BP=op, addr,
        C(1 + i, 1, c)                     #   delta, send delta, south
    C(8, 2, '+')                           # A = delta + prev = addr
    C(8, 3, 'M')                           # B = addr
    C(8, 4, 'd')                           # op>0 -> cw(south->west) = WRITE
    C(7, 4, '1'); C(6, 4, 's')             # send op = 1
    C(5, 4, 'r'); C(4, 4, 's')             # read the value, send it
    C(3, 4, 'v')                           # WRITE arm drops to the merge row
    C(8, 5, '<')                           # READ arm turns west immediately
    C(7, 5, '0')                           #   A = 0 on the westward run
    C(6, 5, 's')                           #   send op = 0 (no value follows)
    C(5, 5, ' '); C(4, 5, ' ')
    C(3, 5, '<')                           # shared rejoin: turns the write man,
                                           # no-op for the read man
    C(2, 5, ' ')
    C(1, 5, '^')
    C(1, 4, '1'); C(1, 3, '+'); C(1, 2, 'M')
    for y in (2, 3, 4):
        C(2, y, ' ')
    for x in (3, 4, 5, 6, 7):
        C(x, 2, ' '); C(x, 3, ' ')

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
    out = os.path.join(os.path.dirname(__file__), 'rewind-v14.man')
    prog.save(out)
    print(out, prog.footprint())
