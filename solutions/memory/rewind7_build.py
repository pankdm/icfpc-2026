#!/usr/bin/env python3
"""memory rewind v7 -- v6 with MEM restructured from 2 rings x 4 relays to
4 rings x 2 relays.  Same 27x27 box, same `M8W/` arithmetic (R*n = 8).

    2 x 4 (v6)   lap 2n+6 = 14   8/14 = 0.571 val/tick   1.75 t/value
    4 x 2 (v7)   lap 2n+6 = 10   8/10 = 0.800 val/tick   1.25 t/value

*** THE FORK SPINE -- the blocker v6's header left open. ***
`Y` births the RIGHT copy one cell clockwise of the parent's heading and the
LEFT copy one cell counter-clockwise, each facing away from the `Y`, and
neither executes its birth cell until the next tick.  A SOUTH-heading parent
therefore births

    right copy -> one cell WEST, heading WEST   (keeps creation order = older)
    left  copy -> one cell EAST, heading EAST   (newest)

which is exactly the pair of headings the two ring flavours want:

  * `vring`'s guard `a` at (down,top) wants a WESTBOUND arrival: BP>0 turns it
    ccw (west->south) into the ring, BP==0 walks it west onto the exit cell.
  * `vring_mirror`'s guard `d` at (down,top) wants an EASTBOUND arrival.

So a west copy born DIRECTLY ONTO an `a` guard, and an east copy born directly
onto a `d` guard, both enter their rings correctly -- and the BP==0 bypass
still works, because the copy executes the guard with its birth heading.
That is what v6's header could not find: the copies never travel past another
ring's guard, so the "four westbound guards cannot share one row" objection
disappears, and no birth cell is ever a wall.

The remaining trick is chaining three forks out of one man.  Both copies of a
fork leave the spine, so the spine advances by a STAIRCASE: one copy enters a
ring, the other walks one cell sideways onto a `v` and drops a row to the next
`Y`.  Three forks, four men, all inside cols 12-20 / rows 4-11:

        col   12 13 14 15 16 17 18 19 20
  row 3                     v                 (b at 15, from row 3's `/`)
  row 4    <  a  .  .  Y  .  v                 fork1: W->MAIN, E->east arm
  row 5    d  v  |  |  v  .  Y  d  H           fork2: W->west arm, E->h3
  row 6    .  m  H  a  Y  d  H  v  a           fork3: W->h1,     E->h2
  row 7    s  r  d  v     v  a  m  .
  ...
  row 9    ^  <              (MAIN bottom)
  row 10                     >  ^              (h3 bottom)
  row 11         ^  <  >  ^                    (h1, h2 bottoms)

MAIN = vring(13,12,top=4) keeps top=4 because its west exit must land on
(11,4)=`W`, (10,4)=`b`, (9,4)= the remainder ring's guard, and that ring's
bottom (top+4) must stay above the read arm on row 9.

*** HELPERS RETIRE ON THEIR OWN EXIT CELL. ***
A helper's merged exit/bypass cell (up,top) is simply `H` instead of `<`/`>`:
the ring exit and the BP==0 bypass both land there and both should retire.
That removes every horizontal run a helper would otherwise have to walk to
reach a shared `H`, and with it every "helper's exit row crosses another
ring's columns" constraint -- which is what lets all four rings sit in eight
adjacent columns with only rows 4-11.

*** THIS BUILD DOES NOT WORK -- IT IS KEPT FOR THE SPINE, NOT THE RESULT. ***
It grades 2/7: it passes the two all-zero cases and diverges on every case
whose answer depends on belt order.  The GEOMETRY above is correct and
reusable; what kills it is throughput, below.  The shipped build is v10
(3 rings), and its header carries the ring-rate arithmetic.  Nothing here
regenerates a .man on purpose -- run it only if you have raised HOP past
0.800 val/tick and want the four-ring spine back.

*** WHY IT FAILS: THE BELT IS A LOOP, SO THE RATE IS min(MEM, HOP). ***
The belt is a loop: MEM pulls from p2 and pushes to p1, HOP pulls from p1 and
pushes to p2, so the sustained rate is min(MEM, HOP).  v6's HOP is two 2x8
rings at 5 pairs / 16-tick lap = 0.625 val/tick, chosen to sit just above
MEM's 0.571.  Four MEM rings demand 0.800, so the *unmodified* HOP would not
merely cap the win -- it would break correctness:

  pipe contention is strict oldest-first, so a 0.625 supply against a 0.800
  demand does not slow the four men evenly.  MAIN (oldest) still gets its
  0.200, and so do the next two; the YOUNGEST helper gets the 0.025 that is
  left and effectively stops.  It is then still inside its ring when MAIN
  comes back round to fork the next command's helpers -- two men in one ring,
  which docs/multi-man-interactions.md 4b kills silently.

HOP's ceiling is 0.625 as v6 shipped it, and 0.750 once its spawn fork is
moved onto a ring corner (see rewind10_build.py).  Neither clears 0.800, and
HOP cannot be widened past W=8: col 25 is the belt's descent and col 14 is
p1, so its room is pinned at 10 columns.  Four rings therefore need a HOP
redesign that does not exist yet.  Also note this spine wants NINE columns
(eight ring columns plus a spine column) and MEM has only nineteen interior
columns after the width fold, so it additionally needs the 27-wide box back.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from littleman import Program
from rewind2_build import vring, vring_mirror, hop, relay_run

X_OUT, X_CMD, X_P2, X_P1 = 1, 4, 9, 14
MEM_W, MEM_H = 22, 14          # interior cols 1..20, rows 1..12
PIPE_ROW = MEM_H


NRINGS = 4                     # 4 rings x 2 relays; divisor = 2*NRINGS


def build():
    p = Program()
    P = p.put

    # ================= MEMORY : cols 0-21, rows 0-13 =================
    p.room(0, 0, MEM_W, MEM_H)

    # -- init: setup SHARES row 1 with the send run --
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
    for i, c in enumerate("rM`100`W%M%dW/" % (2 * NRINGS)):
        P(2 + i, 3, c)
    P(15, 3, 'b')                          # BP = a (every copy inherits it)
    P(16, 3, 'v')

    # -- the fork staircase: 3 `Y`s -> 4 men, one per ring --
    P(16, 4, 'Y')                          # fork1
    P(15, 4, ' '); P(14, 4, ' ')           #   right copy walks west onto MAIN
    P(17, 4, ' '); P(18, 4, 'v')           #   left copy drops to fork2
    P(18, 5, 'Y')                          # fork2
    P(17, 5, ' '); P(16, 5, 'v')           #   right copy drops to fork3
    P(16, 6, 'Y' if NRINGS >= 4 else '<')  # fork3 (or just steer west)

    # -- the four counted rings, 2 relays each, lap 10 --
    vring(P, 13, 12, 4, 2)                 # MAIN, exits west on row 4
    vring(P, 15, 14, 6, 2); P(14, 6, 'H')  # helper 1 (born at fork3, west)
    if NRINGS >= 4:
        vring_mirror(P, 17, 18, 6, 2); P(18, 6, 'H')   # helper 2 (fork3, east)
    vring_mirror(P, 19, 20, 5, 2); P(20, 5, 'H')   # helper 3 (fork2, east)

    # -- MAIN carries on west: r8 remainder ring, then the tap --
    P(11, 4, 'W')                          # A = r8 (B survived the relays)
    P(10, 4, 'b')                          # BP = r8
    vring(P, 9, 8, 4, 1)                   # remainder ring: 1 relay / 8-cell lap
    for x in range(5, 8):
        P(x, 4, ' ')
    P(4, 4, 'v')

    # -- tap: read the OP first, then dispatch --
    P(4, 5, 'r')                           # op        (CMD 0 vs P2 5)
    P(4, 6, 'X')                           # op=1 -> cw(south->west); 0 -> south
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
    for i, c in enumerate(">@rbr-sv"):
        C(1 + i, 1, c)
    C(8, 2, '+')
    C(8, 3, 'M')
    C(8, 4, 'd')
    C(7, 4, '1'); C(6, 4, 's')
    C(5, 4, 'r'); C(4, 4, 's')
    C(3, 4, 'v'); C(3, 5, ' '); C(3, 6, '<')
    C(8, 5, '0'); C(8, 6, '<')
    C(7, 6, 's')
    for x in (6, 5, 4, 2):
        C(x, 6, ' ')
    C(1, 6, '^')
    C(1, 5, '1'); C(1, 4, '+'); C(1, 3, 'M'); C(1, 2, ' ')
    for y in (2, 3, 5):
        C(2, y, ' ')
    for x in (4, 5, 6, 7):
        C(x, 2, ' '); C(x, 3, ' '); C(x, 5, ' ')
    C(3, 2, ' '); C(3, 3, ' ')

    # ================= HOP : cols 15-24, rows 17-23 =================
    hop(p, P, 15, 17, 8, 5)

    # ================= IO =================
    p.output_room(0, 17)
    p.input_room(0, 24)

    # ================= pipes =================
    out = [(X_OUT, PIPE_ROW), (X_OUT, PIPE_ROW + 2)]
    cmd = [(X_CMD, PIPE_ROW + 2), (X_CMD, PIPE_ROW)]
    ipipe = [(3, 25), (5, 25), (5, 26), (8, 26), (8, 25)]
    p1 = [(X_P1, PIPE_ROW), (X_P1, 15), (16, 15), (16, 16)]
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
    if len(sys.argv) > 1:
        NRINGS = int(sys.argv[1])
    prog = build()
    out = os.path.join(os.path.dirname(__file__), 'rewind-v7.man' if NRINGS >= 4
                       else 'rewind-v7r%d.man' % NRINGS)
    prog.save(out)
    print(out, prog.footprint())
