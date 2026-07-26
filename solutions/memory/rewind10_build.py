#!/usr/bin/env python3
"""memory rewind v10 -- v8's 26x26 layout with both ends of the belt loop
retuned: HOP 0.625 -> 0.750 val/tick, MEM 0.571 -> 0.600, three rings of two
relays instead of two rings of four (`M6W/`, not `M8W/`).

*** THE BELT IS A LOOP, SO THE SUSTAINED RATE IS min(MEM, HOP). ***
MEM pulls from p2 and pushes to p1; HOP pulls from p1 and pushes to p2.  Any
MEM speed-up past HOP's ceiling does not merely fail to pay -- it BREAKS
CORRECTNESS.  Pipe contention is strict oldest-first, so an over-subscribed p2
is not shared evenly: the oldest man keeps its full share and the youngest is
starved to a standstill, still inside its ring when the next command forks a
fresh man into it, and two men in one ring kill each other silently
(multi-man-interactions.md 4b).  MEASURED: a 4-ring MEM (0.800 demanded
against the old 0.625 ceiling) grades 2/7 -- it passes the all-zero cases and
diverges on every case whose answer depends on belt order.  So HOP first.

*** HOP: 0.625 -> 0.750, BY MOVING THE FORK ONTO A RING CORNER. ***
HOP is two 2xW rings joined by a spawn lane holding `@` and one `Y`.  `Y`
births north and south of an eastbound parent, so both birth cells land ON the
rings and must hold a glyph rather than a blank.  With the fork at C=5 those
cells were interior cells of the relay runs: each consumed a slot that could
have been a relay AND left an odd-length run on either side of it, so a ring
carried 5 pairs per 16-tick lap instead of 6.  Putting the fork at C=W lands
both births on ring CORNERS -- cells that are already turns and were never
going to be relays.  The copy born at (W,2) executes ring A's own `<`, the copy
born at (W,4) ring B's own `v`, and both relay runs stay even at 6 cells:
6 pairs x 2 rings / 16 ticks = 0.750, for a one-cell change.  Verified in
isolation: identical 7/7 and identical avgTicks, since MEM was still the
bottleneck -- it buys headroom, not ticks.

*** MEM: THREE RINGS OF TWO, NOT TWO OF FOUR. ***
A counted ring's lap is 2n+6, so R rings of n relays sustain R*n/(2n+6), all
arithmetic-neutral as long as the divisor tracks R*n:
    2 x 4 (v6/v8)  lap 14   8/14 = 0.571
    3 x 2 (here)   lap 10   6/10 = 0.600   <- 20% clear of HOP's 0.750
    4 x 2          lap 10   8/10 = 0.800   <- over the ceiling, see above
DO NOT try to shorten the lap below 2n+6 by merging the exit test into the
bottom turn.  I tried: `d` at the top of the return column fires cw(north->
east) and drops the man onto `m` HEADING EAST, and `m` is not a turn, so he
walks straight out of the ring's two columns.  The `v` re-entry cell that
looks redundant is what turns him south.  2n+6 is a real floor for a
two-column ring, and the build times out at 5M ticks if you ignore it.

*** THE FORK SPINE FOR THREE RINGS -- the piece v6's header left open. ***
`Y` births the RIGHT copy one cell clockwise of the parent's heading and the
LEFT copy one cell counter-clockwise, each facing away from the `Y`.  A
SOUTH-heading parent therefore births

    right copy -> one cell WEST, heading WEST   (keeps creation order, older)
    left  copy -> one cell EAST, heading EAST   (newest)

which is exactly the pair of headings the two ring flavours want: `vring`'s
guard `a` wants a WESTBOUND arrival, `vring_mirror`'s guard `d` an EASTBOUND
one.  A copy born directly onto its guard executes it with its birth heading,
so it enters the ring correctly AND still takes the BP==0 bypass when the
rotation is short.  No copy ever walks past another ring's guard, which is
what made "four westbound guards cannot share one row" look fatal.

Two forks, three men, in cols 12-18 with col 16 as the spine:

    fork1 (16,4): west copy walks row 4 to MAIN's guard at (13,4); east copy
                  steps to (18,4) and doubles back along row 5 to fork2.
    fork2 (16,6): west copy is born ON h1's guard (15,6), east copy ON h2's
                  guard (17,6).

The rings are staggered so every spine cell sits ABOVE the ring whose column
it borrows: MAIN tops at row 4 (it must exit west onto `W`/`b` and the
remainder ring, whose bottom has to stay above the read arm on row 9), h1 and
h2 top at row 6, leaving rows 4-5 of cols 14/15 and 17/18 free for the spine.
Helpers retire on their own merged exit/bypass cell (`H` instead of `<`/`>`),
so no helper needs a horizontal run to reach a shared `H` -- which is what
lets three rings and a spine fit in seven columns.
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
    hop(p, P, 15, 16, 8, 8)
    P(15 + 8, 16 + 4, 'v')                 # ring B's own corner, not hop()'s `>`

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
    out = os.path.join(os.path.dirname(__file__), 'rewind-v10.man')
    prog.save(out)
    print(out, prog.footprint())
