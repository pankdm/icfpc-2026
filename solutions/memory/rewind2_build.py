#!/usr/bin/env python3
"""memory rewind v2 -- STEP (1): test-before-fork vertical rings.

Same protocol as rewind-v1 (CONTROL ships [delta, value, op]; MEMORY is
stateless and rotates a 100-value belt), but MEMORY's two do-while rings are
replaced by VERTICAL 2-column rings whose guard-bypass and ring-exit MERGE on
a single cell.  Consequences:
  * rot==0 / r8==0 run no lap at all -- correct BY CONSTRUCTION, so v1's
    separate bypass lanes (row 6 cols 7-15, row 9 cols 7-10, col 11 rows
    10-12, row 13 cols 6-10) are deleted outright;
  * the rings cost 2 COLUMNS instead of 11, which is what makes the later
    fold possible (box is width-driven).

PIPE BINDING IS THE WHOLE GAME HERE.  `r`/`s` lock onto the *nearest* pipe
(Manhattan to the segment attached to the room, reading-order ties).  All four
of MEMORY's pipes attach to its bottom wall, so binding is decided by column:

    OUT x=1      CMD x=6      P2(belt in) x=10      P1(belt out) x=16

  -> CMD/P2 midpoint x=8   : `r` at x<=7 reads COMMANDS, at x>=9 reads BELT
  -> OUT/P1 midpoint x=8.5 : `s` at x>=9 sends to the BELT (never to output)

Every pipe instruction below is placed to satisfy that, with the margin noted.
Moving any of these columns silently re-binds instructions -- re-check before
touching them.

STATUS: 7/7 public + 34/34 fuzz streams (scratchpad/rewind/fuzz.py).
        box 1764 (32x42), avgTicks 5351, local 9.44M  (~4.18x -> ~39M server).
        Champion addr-compare is 3.96M local / 15.92M server; leader 9.55M.

WHAT STEP (1) DID AND DID NOT BUY -- measured, don't re-litigate:
  * box 2500 -> 1764 came ENTIRELY from shortening the belt (235 -> 117 cells).
  * ticks did NOT improve (5288 -> 5351). The bypass lanes this deleted were
    simply replaced by a ~32-tick return corridor (up col 17, west along row 4).
    Per-op cost is still ~240 ticks, split roughly:
        row 5 compute        16
        row 6 + ring walk    10
        ring8   a * 22       ~131   (a = rot>>3, avg 5.94; 2.75 ticks/relay)
        ring1   r8 * 10      ~35    (r8 avg 3.5; 10 ticks/relay -- WORST cell)
        tap                  ~22
        return corridor      ~32
  * so the remaining tick levers, in order of value:
      1. ring1 is 10 ticks/relay. Kill the separate remainder ring entirely by
         entering the MAIN ring at a variable offset so the first partial lap
         performs exactly r8 relays (entry cells: up-col rows top+4/6/8/10 for
         1..4 relays, down-col rows top+9/7/5/3 for 5..8). Always enter on an
         'r', never mid-relay. Worth ~20 ticks/op.
      2. the return corridor (~32) is pure geometry -- it shrinks with the fold.
      3. a bigger ring amortises the 6 fixed cells/lap: ticks/relay = 2 + 6/R
         for R relays per lap (R=8 -> 2.75, R=16 -> 2.375). R=16 needs 20 rows.
    A single man on a straight rsrsrs chain is exactly 0.50 values/tick
    (2 ticks/relay), so ~2.1-2.4 ticks/relay is the realistic floor here.

*** THE cmd/(3,21) CONFLICT IS SOLVED, AND A HARDER BLOCKER FOUND. ***
cmd fix: route it BELOW HOP, not beside it. With MEM cols 0-16 rows 0-17,
HOP at cols 4-15 rows 20-23 and p1 = [(14,18),(14,19)] (2 cells into HOP's top
wall), cmd = [(16,25),(3,25),(3,18)] runs west along row 25 under HOP and north
up the free col 3. No collision: output room is cols 0-2, HOP is cols 4-15.

THE REAL BLOCKER -- CONTROL'S *WIDTH* ISOLATES THE BELT, not its area:
lay out 27x27 as MEM cols 0-16 rows 0-17, CONTROL cols 17-26 rows 18-26. Then
  * right strip  = cols 17-26, rows 0-17   (180 cells)
  * bottom-left  = cols 0-16,  rows 18-26  (153 cells)
and these two regions are ONLY DIAGONALLY adjacent, at (16,17)/(17,18). Every
orthogonal crossing is blocked: (16,17) is MEM's bottom-right corner and
(17,18) is CONTROL's top-left corner. So a pipe cannot pass between them.
The belt serpentine must then fit entirely in the bottom-left, which after
HOP (48), the output room (9), cmd (~20), OUT and p1 leaves only ~72 free
cells -- and p2 needs ~105. The fold fails by ~33 cells no matter how neatly
MEM is packed.

=> CONTROL must be at most 8 WIDE (cols 19-26), which opens a 2-wide channel at
   cols 17-18 rows 18-26 joining the right strip to the bottom. Shrinking
   CONTROL is therefore not an area optimisation, it is a CONNECTIVITY
   requirement. Do it first; nothing else about the 27x27 fold works without it.
   CONTROL is ~19 ops (10 main + 'd' + two 4-op arms) plus ~7 turns, so a
   2-wide loop needs ~13 rows: about 4x15, or 5x11 if laid 3 wide. Either is
   <= 8 wide and both beat the current 10x9=90.

MEASURED DUAL-PUMP (from the primitives agent; adopt in the rings):
  1 man = 0.500 val/tick, 2 men = 1.000, 3 men WORSE than 2 (strict ascending-id
  contention starves the third). Birth cell must be non-blank -- a blank one
  lets the clone fly into a wall. Order is preserved because 'r' immediately
  followed by 's' forces send == receive + 1.
  NOTE the 1.0 figure is for a straight rsrs chain. In a RING it is
  2/(2 + 6/nrelay) = 0.727 at nrelay=8, since the lap still pays 'm', 'd' and
  three turns; rotation ~143 -> ~69 t/op, i.e. ~166 t/op overall. HOP must be
  pumped too or it becomes the limiter at 0.35 val/tick.

NEXT STEP -- NARROW MEM TO 17 WIDE, THEN FOLD TO 27x27. Fully derived, and it
is the ONLY thing standing between here and beating the champion:
  At avgTicks 5210, box 729 (27x27) = 3.80M local < champion 3.96M. Box 784
  (28x28) = 4.08M is NOT enough, so 27x27 is the target, not "about 28".
  With MEM 19 wide the best reachable box is 29x29 = 4.38M (a LOSS): CONTROL's
  10x9 rectangle needs either a 10-wide side strip or a 9-tall bottom strip,
  and at box 27 with MEM 19 wide neither exists. Narrow MEM to 17 and the right
  strip becomes cols 17-26 = exactly 10 wide, so CONTROL drops in at rows 0-8.

  MEM room(0,0,17,21); interior cols 1-15, rows 1-19. Attachments on the bottom
  wall: OUT=1, CMD=3, P2=9, P1=14.
    -> CMD/P2 midpoint 6  : `r` at x<=5 reads COMMANDS, at x>=7 reads BELT
                            (x=6 TIES and CMD wins on reading order -- avoid it)
    -> OUT/P1 midpoint 7.5: every `s` must sit at x>=8
  Row 5 (15 cells, cols 1-15): > r M ` 1 0 0 ` W % M 8 W / v   -- 'b' moves to
  row 6 because col 16 no longer exists.
  Row 6 westward: (15,6)'<' (14,6)'b' (13,6)'a'=guard8 -> ring8 cols 12/13,
  exit (12,6); (11,6)'W' (10,6)'b' (9,6)'a'=guard1 -> ring1 cols 8/9, exit
  (8,6); then west to the tap. Checked: ring8 s->P1 dist 1-2 vs OUT 11-12;
  ring8 r->P2 dist 3-4 vs CMD 9-10; ring1 s->P1 5-6 vs OUT 7-8 (margin 2);
  ring1 r->P2 0-1. All bind correctly.
  Tap at cols 4-9: (5,7)'r'(second) (5,8)'M' (5,9)'r'(op) (5,10)'X'.
  Init: use `20` and 5 sends/lap x 20 laps = 100, ring cols 8-14 rows 2-3, so
  every init `s` stays at x>=8.
  RETURN WEST, NOT EAST -- this is also worth ~10 t/op over the current route:
  read arm ... (9,11)'v' down col 9 to (9,18)'<', west along row 18 to
  (1,18)'^', north up col 1, and (1,5)'>' turns it straight back into row 5.
  Write arm rejoins row 18 at (10,18)'<'. Col 1 rows 6-17 and col 9 rows 12-17
  are both free (ring1 is rows 6-10, ring8 cols 12-13).
  Then: CONTROL cols 17-26 rows 0-8; input room cols 17-19 rows 11-13 with
  ipipe [(18,10),(18,9)]; HOP cols 8-19 rows 23-26 (NOT 21-24, which would sit
  on the row-21 attachment cells); output room cols 0-2 rows 23-25.
  UNSOLVED: cmd must reach (3,21) from CONTROL without crossing p1's (14,22).
  Routing cmd along row 22 collides with p1; along row 21 it collides with the
  other three attachments. Either give p1 a different exit row or run cmd down
  col 1-2 on the far side. Solve this before building.

WHY THE OLD "688-CELL FLOOR" NOTE BELOW IS WRONG (kept as a warning):
it summed room BOUNDING RECTANGLES. rewind-v2 has only 431 non-space cells at
32% density, 269 of them walls. The rooms are bloated around empty interiors,
so the fix is to SHRINK ROOMS, not to pack the current rectangles tighter.
(The packing constraint really is the sum of rectangles, since a room's blank
interior cannot host another room or a pipe -- but those rectangles are the
thing to shrink.)

THE OLD, OVERSTATED AREA ARGUMENT:
  MEM 19x21=399 + CONTROL 10x9=90 + HOP 12x4=48 + 2 IO rooms=18 + pipes ~133
  = 688 cells of content. A 26x26 box is 676 -- it DOES NOT FIT. 27x27=729
  leaves 41 cells of slack, i.e. ~94% packing, which is not routable.
  So beating the champion needs one of:
    (a) shrink MEM (399 is the dominant term; its interior is mostly blank
        corridor), or
    (b) cut ticks so the box target relaxes (box = 9,547,949 / (92 * t_per_op)).
  Attachment columns are the trap: putting CMD on MEM's right wall to free the
  bottom row was tried on paper and re-binds the ring 'r' cells to CMD (ring at
  (10,9) is 10 from a right-wall CMD but 12 from P2) -- fatal and silent.
  Any layout move MUST be re-checked against the midpoint rule above and then
  re-fuzzed, not just re-graded on the 7 public cases.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools'))
from littleman import Program

# MEMORY bottom-wall pipe attachment columns (see module docstring).
X_OUT, X_CMD, X_P2, X_P1 = 1, 6, 10, 16
MEM_W, MEM_H = 19, 21          # room(0,0,MEM_W,MEM_H) -> interior 1..17 x 1..19
MEM_BOT = MEM_H - 1            # bottom wall row 20
PIPE_ROW = MEM_H               # attachment cells sit on row 21


def vring(P, down, up, top, nrelay):
    """Vertical 2-column ring with a MERGED guard-bypass / ring-exit cell.

    The man arrives WESTBOUND on row `top`.  `down` is the southbound column,
    `up` (== down-1) the northbound one.

        (down, top)   'a'  guard : BP>0 -> ccw(west->south) into the ring
                                   BP==0 -> straight west onto the exit cell
        (up,   top)   '<'  exit  : ring-exit (from the north) and guard-bypass
                                   (from the east) MERGE here, both heading west

    Returns the bottom row used.  `nrelay` relays per lap, laid out so every
    'r' is IMMEDIATELY followed by its 's' (that adjacency is what keeps belt
    ORDER correct: send time == receive time + 1).
    """
    # 2*nrelay relay CELLS split over the two columns; each column's run must
    # be EVEN so it starts on 'r' and ends on its matching 's' (never split a
    # relay across the bottom turn).  nrelay=1 therefore puts both cells on the
    # down column and leaves the up column a bare return corridor.
    dn = 2 * ((nrelay + 1) // 2)       # relay cells on the southbound column
    upn = 2 * nrelay - dn              # relay cells on the northbound column
    # A lap costs 2*nrelay relay cells + 'm' + 'd' + three turns ('v','<','^'),
    # so lap >= 2*nrelay + 6 and ticks/relay >= 2 + 6/nrelay -- 2.75 at nrelay=8.
    # 'm' only has to run once per lap, so put it on whichever column has a
    # spare cell.  When the up column is shorter than the down one (nrelay odd,
    # notably the nrelay=1 remainder ring) it has a free slot, which pulls the
    # bottom turn up a row and makes the lap 8 cells instead of 10.
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

    # ================= MEMORY : cols 0-18, rows 0-20 =================
    p.room(0, 0, MEM_W, MEM_H)

    # -- init: A=10, BP=10, A=0, then 10 laps x 10 sends of 0 = 100 zeros --
    for i, c in enumerate("@`10`b0v"):
        P(1 + i, 1, c)
    P(8, 2, '>')
    for i, c in enumerate("ssssss"):       # cols 9-14, all x>=9 -> belt
        P(9 + i, 2, c)
    P(15, 2, 'v'); P(15, 3, '<')
    for i, c in enumerate("ssss"):         # cols 14-11, all x>=9 -> belt
        P(14 - i, 3, c)
    P(10, 3, 'm'); P(9, 3, ' '); P(8, 3, 'd')
    P(7, 3, 'v'); P(7, 4, '<'); P(1, 4, 'v')

    # -- row 5: delta -> rot -> split rot = 8a + r8, BP := r8 --
    # r:A=delta  M:B=delta  `100`:A=100  W:A=delta,B=100  %:A=rot
    # M:B=rot  8:A=8  W:A=rot,B=8  /:A=a,B=r8  W:A=r8,B=a
    P(1, 5, '>')
    for i, c in enumerate("rM`100`W%M8W/W"):
        P(2 + i, 5, c)
    P(16, 5, 'v')

    # -- row 6: the two rings, flowing WESTWARD --
    P(16, 6, '<')
    P(15, 6, 'b')                          # BP = r8
    bot1 = vring(P, 14, 13, 6, 1)          # remainder ring: 1 relay / 8-cell lap
    P(12, 6, 'W')                          # A = a  (B survived the relays)
    P(11, 6, 'b')                          # BP = a
    bot8 = vring(P, 10, 9, 6, 8)           # main ring: 8 relays / 22-cell lap
    P(8, 6, ' '); P(7, 6, 'v')

    # -- tap: read the command pair, dispatch on op --
    P(7, 7, 'r')                           # second value (CMD: 1 vs P2 3)
    P(7, 8, 'M')                           # B = value
    P(7, 9, 'r')                           # op            (CMD: 1 vs P2 3)
    P(7, 10, 'X')                          # op=1 -> cw(south->west); op=0 -> south
    for y in range(11, 18):
        P(7, y, ' ')
    # READ arm (op == 0): tap the belt, output AND reinject
    P(7, 18, '>')
    for x in range(8, 11):
        P(x, 18, ' ')
    P(11, 18, 'r')                         # belt value   (P2: 1 vs CMD 5)
    P(12, 18, 'S')                         # -> output pipe AND belt (reinject)
    for x in range(13, 17):
        P(x, 18, ' ')
    P(17, 18, '^')
    # WRITE arm (op == 1): discard the old belt value, send the new one
    P(6, 10, 'v')
    for y in range(11, 19):
        P(6, y, ' ')
    P(6, 19, '>')
    for x in range(7, 11):
        P(x, 19, ' ')
    P(11, 19, 'r')                         # old value, discarded
    P(12, 19, 'W')                         # A = value (from B)
    P(13, 19, 's')                         # -> belt      (P1: 3 vs OUT 12)
    for x in range(14, 17):
        P(x, 19, ' ')
    P(17, 19, '^')
    # -- return: up the free col 17, then west along row 4 into row 5 --
    for y in range(5, 18):
        P(17, y, ' ')
    P(17, 4, '<')
    for x in range(8, 17):
        P(x, 4, ' ')
    for x in range(2, 7):
        P(x, 4, ' ')

    # ================= CONTROL : cols 0-9, rows 33-41 =================
    CX, CY = 0, 33
    C = lambda x, y, c: P(CX + x, CY + y, c)
    p.room(CX, CY, 10, 9)
    for i, c in enumerate(">@rbr-sv"):     # op, BP=op, addr, A=addr-prev, send
        C(1 + i, 1, c)
    for i, c in enumerate("+M1+M<"):       # A=addr, B=addr, then prev := addr+1
        C(8, 2 + i, c)                     # (+1 because the tap reinject also
    C(7, 7, 'd')                           #  advances the belt by one)
    C(7, 6, 'r'); C(7, 5, 's'); C(7, 4, '<')          # WRITE arm: value, then 1
    C(6, 4, '1'); C(5, 4, 's'); C(4, 4, '<'); C(3, 4, '<'); C(2, 4, 'v')
    C(2, 5, ' '); C(2, 6, ' ')
    C(6, 7, '0'); C(5, 7, 's'); C(4, 7, '0'); C(3, 7, 's')   # READ arm: 0, 0
    C(2, 7, '<'); C(1, 7, '^')
    for y in range(2, 7):
        C(1, y, ' ')

    # ================= HOP : cols 20-31, rows 22-25 =================
    HX, HY = 20, 22
    H = lambda x, y, c: P(HX + x, HY + y, c)
    p.room(HX, HY, 12, 4)
    H(1, 1, '>'); H(2, 1, '@')
    for i, c in enumerate("rsrsrsr"):
        H(3 + i, 1, c)
    H(10, 1, 'v'); H(10, 2, '<')
    for i, c in enumerate("srsrsrs"):
        H(9 - i, 2, c)
    H(2, 2, ' '); H(1, 2, '^')

    # ================= IO =================
    p.output_room(0, 23)
    p.input_room(12, 33)

    # ================= pipes =================
    out = [(X_OUT, PIPE_ROW), (X_OUT, PIPE_ROW + 1)]
    cmd = [(X_CMD, 32), (X_CMD, PIPE_ROW)]
    ipipe = [(11, 34), (10, 34)]
    p1 = [(X_P1, PIPE_ROW), (X_P1, 23), (19, 23)]
    # Belt return: serpentine in rows 27-31 over cols 11-31, then north up the
    # deliberately-kept-clear col 10.  The FIRST segment must run SOUTH so the
    # start cell's backward neighbour is (25,25) = HOP's bottom wall; a westward
    # first segment points its backward neighbour at empty space and HOP then
    # has no outgoing pipe at all (fatal no-pipe on its first 's').
    p2 = [(25, 26), (25, 27), (11, 27), (11, 28), (31, 28), (31, 29),
          (11, 29), (11, 30), (31, 30), (31, 31), (10, 31),
          (X_P2, PIPE_ROW)]
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
    out = os.path.join(os.path.dirname(__file__), 'rewind-v2.man')
    prog.save(out)
    print(out, prog.footprint())
