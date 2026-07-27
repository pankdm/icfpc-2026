#!/usr/bin/env python3
"""memory rewind SLIM -- DOES NOT WORK, kept for the two rules it measured.

It builds and LOADS at 23x24, but every case times out, because both belt pipes
get shredded into a dozen phantom pipes.  That exposed the parser rule nothing
in docs/ had written down:

*** A PIPE CELL ADJACENT TO A ROOM, WHOSE FLOW POINTS AWAY FROM THAT ROOM, IS
    AN ATTACHMENT CANDIDATE.  The parser scans candidates in READING ORDER and
    traces from the first one it finds. ***

  - A pipe's real SOURCE cell must therefore leave the wall PERPENDICULAR.  p2
    sourced from HOP's bottom wall with a westward arrow (flow parallel to the
    wall) was not recognised at all, so the parser fell back on the phantoms
    and cut p2 into ten pipes, all ending at MEM.
  - Flush lanes are usable as INTERMEDIATE cells (rewind-incell's p2 hugs three
    walls) only while the real source is EARLIER in reading order.  That is why
    `scratchpad/rewind/longp1.py` fails: its p1 runs up col 19 flush against
    MEM's east wall and turns east at (19,0), a phantom source on row 0, which
    beats p1's real source at (14,13) and splits the pipe.
  - Consequence: a flush lane beside a room is a DEAD END for a through-route.
    Entering or leaving it needs a perpendicular move, and that move is either
    a phantom source (pointing away) or a phantom terminal (pointing in).

The geometry below is still correct and reusable: MEM's interior does fit in 16
columns if the remainder ring slides to cols 6/7, and p1 may legally run east
along row 13 flush under MEM because MEM is p1's SOURCE.  What kills it at
23 columns is the BOTTOM band, not MEM: OUT/IN(3) + CONTROL(10) + corridor(2)
+ HOP(8) + p2's descent column(1) = 24 all by itself, and narrowing MEM does
nothing for that.

Original design note follows.

memory rewind SLIM -- rewind-incell with MEM one column narrower (19 -> 18).

The column comes from the two BLANK glide cells on row 4 between the tap drop
and the remainder ring's exit.  rewind-incell's row 4 reads

    (4)v  (5)_  (6)_  (7)< (8)a  (9)b (10)W (11)< (12)a (13)Y (14)> (15)v

-- the remainder ring sat at cols 7/8 only because the OUT/P1 binding midpoint
was 7.5, so an `s` west of col 8 would have sent the belt value to the OUTPUT
room.  That midpoint is not a law of physics, it is `X_OUT`/`X_P1`, and both
are free parameters.  Sliding the ring to cols 6/7 and re-solving the four
attachment columns pulls the whole east block one column west:

    (4)v  (5)_  (6)< (7)a  (8)b  (9)W (10)< (11)a (12)Y (13)> (14)v

so MAIN lands on cols 10/11, fork1 on col 12, fork2 on col 14, helper1 on
cols 12/13 and helper2 on cols 15/16.  MEM's interior is 16 wide, MEM is 18,
and the whole belt/HOP block shifts west with it: 24 -> 23 columns.

MAIN moving west also moves its ring INTO the read arm's old drop column, so
rows 9/10 are re-laid: the read arm now drops at col 9 onto the write arm's
own turn cell (a `v` is a no-op for a man already heading south), exactly the
sharing rewind-incell used at col 10.

Binding solution (all four pipes attach on row 13, so |y-13| cancels and only
columns decide):

    X_OUT=1  X_CMD=4  X_P2=6  X_P1=9
    CMD/P2 midpoint 5.0 -> `r` at x<=4 reads COMMANDS, x>=6 the BELT
    OUT/P1 midpoint 5.0 -> every `s` sits at x>=7, so all sends reach the belt

p1 no longer drops straight down: it runs EAST along row 13, flush against
MEM's bottom wall.  That is legal because MEM is p1's SOURCE -- the flush rule
only forbids intermediate cells beside the room a pipe TERMINATES at -- and it
keeps row 14 clear for p2.  p2 in turn takes its westward leg on row 15, above
CONTROL's top wall, which CONTROL is not an endpoint of.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from littleman import Program
from rewind2_build import vring, vring_mirror, hop

X_OUT, X_CMD, X_P2, X_P1 = 1, 4, 6, 9
MEM_W, MEM_H = 18, 13          # interior cols 1..16, rows 1..11
PIPE_ROW = MEM_H               # attachment cells sit on row 13
ROOM_Y = 16                    # CONTROL / HOP / OUT top wall row
BOT = 23                       # bottom-most grid row (p2's return leg)


def build():
    p = Program()
    P = p.put

    # ================= MEMORY =================
    p.room(0, 0, MEM_W, MEM_H)

    # -- rows 1-2: init, folded over both rows (20 laps x 5 sends = 100 zeros)
    for i, c in enumerate("@`20`b0"):      # cols 1-7: A=20, BP=20, A=0
        P(1 + i, 1, c)
    P(8, 1, '>')                           # loop re-entry
    for i, c in enumerate("sss"):          # cols 9-11
        P(9 + i, 1, c)
    P(12, 1, 'v'); P(12, 2, '<')
    P(11, 2, 's'); P(10, 2, 's')
    P(9, 2, 'm'); P(8, 2, 'd')
    for i, c in enumerate("`001`"):        # B = 100 for the FIRST lap only
        P(3 + i, 2, c)
    P(2, 2, 'M')
    P(1, 2, 'v')

    # -- row 3: delta -> rot = 6a + r6 --
    P(1, 3, '>')                           # init drop re-entry
    P(2, 3, '>')                           # return-climb re-entry
    for i, c in enumerate("r%M6W/"):
        P(3 + i, 3, c)
    P(9, 3, ' '); P(10, 3, ' ')
    P(11, 3, 'b')                          # BP = a, hoisted above fork1
    P(12, 3, 'v')

    # -- rows 4-11: remainder ring, MAIN, fork spine, two helper rings --
    P(12, 4, 'Y')                          # fork1: west copy lands on MAIN's guard
    P(13, 4, '>'); P(14, 4, 'v'); P(14, 5, ' ')
    P(15, 4, ' '); P(16, 4, ' ')
    P(15, 5, ' '); P(16, 5, ' ')
    P(14, 6, 'Y')                          # fork2: births BOTH helper guards
    vring(P, 11, 10, 4, 2)                 # MAIN
    vring(P, 13, 12, 6, 2); P(12, 6, 'H')  # helper 1
    vring_mirror(P, 15, 16, 6, 2); P(16, 6, 'H')   # helper 2
    P(9, 4, 'W')                           # A = r6 (B survived the relays)
    P(8, 4, 'b')                           # BP = r6
    vring(P, 7, 6, 4, 1)                   # remainder ring: 1 relay / 8-cell lap
    P(5, 4, ' ')
    P(4, 4, 'v')

    # -- tap --
    P(4, 5, 'r')                           # op            (CMD 0 vs P2 2)
    P(4, 6, 'X')                           # op=1 -> cw(south->west); 0 -> south
    P(4, 7, ' '); P(4, 8, ' ')
    P(4, 9, '>'); P(5, 9, ' ')
    P(6, 9, 'r')                           # belt value    (P2 0 vs CMD 2)
    P(7, 9, 'S')                           # -> output pipe AND belt (reinject)
    P(8, 9, ' ')
    P(9, 9, 'v')                           # drop onto the write arm's turn cell
    # WRITE arm
    P(3, 6, 'v')
    for y in range(7, 10):
        P(3, y, ' ')
    P(3, 10, '>')
    P(4, 10, 'r')                          # new value     (CMD 0 vs P2 2)
    P(5, 10, 'M')                          # B = value
    P(6, 10, 'r')                          # old value, discarded
    P(7, 10, 'W')                          # A = value
    P(8, 10, 's')                          # -> belt
    P(9, 10, 'v')                          # shared turn cell (no-op for the
    P(9, 11, '<')                          #   read man already heading south)
    # -- return: WEST along row 11, restoring B = 100 on cells already walked --
    for i, c in enumerate("`001`"):
        P(4 + i, 11, c)
    P(3, 11, 'M')
    P(2, 11, '^')
    for y in range(4, 11):
        P(2, y, ' ')
    P(1, 11, ' ')

    # ================= CONTROL : 10x7, cols 3-12 =================
    CX, CY = 3, ROOM_Y
    C = lambda x, y, c: P(CX + x, CY + y, c)
    p.room(CX, CY, 10, 7)
    for i, c in enumerate(">@rbr-sv"):
        C(1 + i, 1, c)
    C(8, 2, '+'); C(8, 3, 'M'); C(8, 4, 'd')
    C(7, 4, '1'); C(6, 4, 's')
    C(5, 4, 'r'); C(4, 4, 's')
    C(3, 4, 'v')
    C(8, 5, '<'); C(7, 5, '0'); C(6, 5, 's')
    C(5, 5, ' '); C(4, 5, ' '); C(3, 5, '<'); C(2, 5, ' '); C(1, 5, '^')
    C(1, 4, '1'); C(1, 3, '+'); C(1, 2, 'M')
    for y in (2, 3, 4):
        C(2, y, ' ')
    for x in (3, 4, 5, 6, 7):
        C(x, 2, ' '); C(x, 3, ' ')

    # ================= HOP : cols 15-22 =================
    hop(p, P, 15, ROOM_Y, 6, 6)
    P(15 + 6, ROOM_Y + 4, 'v')

    # ================= IO =================
    p.output_room(0, ROOM_Y)
    p.input_room(0, ROOM_Y + 5)

    # ================= pipes =================
    out = [(X_OUT, PIPE_ROW), (X_OUT, ROOM_Y - 1)]
    cmd = [(X_CMD, ROOM_Y - 1), (X_CMD, PIPE_ROW)]
    ipipe = [(1, ROOM_Y + 4), (1, ROOM_Y + 3), (2, ROOM_Y + 3)]
    # *** THE BELT IS RE-SPLIT: p1 IS NOW THE LONG PIPE. ***
    # The flush rule is asymmetric -- a pipe may hug the room it STARTS at and
    # only its DESTINATION's walls are poison -- so the two halves of the belt
    # can reach places the other cannot:
    #   p1 starts at MEM, so row 13 (flush under MEM) and col 18 (flush beside
    #     MEM's east wall) are p1's alone; both are dead to p2.
    #   p2 starts at HOP, so row 23 (under HOP) and the corridor col 14 (beside
    #     HOP's west wall) are p2's alone.
    # Giving p1 the whole top-right snake and p2 the bottom loop keeps the two
    # vertex-disjoint without either having to cross the other, which is what
    # the "row 14 is the only corridor" deadlock was really about.
    p1 = [(X_P1, PIPE_ROW), (18, PIPE_ROW), (18, 0),
          (19, 0), (19, 14), (20, 14), (20, 0),
          (21, 0), (21, 13), (22, 13), (22, 14), (21, 14), (21, ROOM_Y - 1)]
    # p2: HOP's BOTTOM wall -> west along the bottom row -> serpentine up the
    # CONTROL/HOP corridor -> zigzag west over rows 14/15 -> down into MEM.
    p2 = [(21, BOT), (13, BOT),
          (13, 22), (14, 22), (14, 21), (13, 21),
          (13, 20), (14, 20), (14, 19), (13, 19),
          (13, 18), (14, 18), (14, 17), (13, 17),
          (13, 16), (14, 16), (14, 15), (13, 15), (13, 14),
          (12, 14), (12, 15), (11, 15), (11, 14),
          (10, 14), (10, 15), (9, 15), (9, 14),
          (8, 14), (8, 15), (7, 15), (7, 14),
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
    out = os.path.join(os.path.dirname(__file__),
                       sys.argv[1] if len(sys.argv) > 1 else 'rewind-slim.man')
    prog.save(out)
    print(out, prog.footprint())
