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

STATUS: 7/7 public + 69/69 fuzz streams (scratchpad/rewind/fuzz.py 60).
        box 1764 (42x42), avgTicks 3984.0, local 7,027,776.
        SUBMITTED and CONFIRMED 24/24, server score 28,186,515
        (the lineage's previous best submission was 34,896,183).
        Champion addr-compare is 3.96M local / 15.92M server; leader 9.55M.

WHERE THE REMAINING VALUE IS.  Ticks are now 3984 and the box is untouched at
1764, so the whole gap to the champion is GEOMETRY.  Fold this to 27x27 (729)
at the current tick count and it lands at 2.90M local, roughly 11.6M server --
that BEATS the champion's 15.92M and gets within striking distance of the
9.55M leader.  Nothing about the engine needs to change to collect that.

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

*** HEIGHT ARITHMETIC FOR THE 28x28 FOLD -- READ BEFORE LAYING IT OUT. ***
The OUT/CMD swap (done) only works while CONTROL stays SOUTH-WEST, so that cmd
runs straight up the far-west column with nothing to cross. Moving CONTROL
north-east to "kill the connector band" re-creates the planarity conflict,
because cmd would again have to cross p1 (x=14) and p2 (x=9). So CONTROL stays
below MEM, and the box height is a pure sum:

    MEM 18 + cmd 2 + CONTROL 9 = 29   ->   box 29x29 = 841

cmd needs TWO cells (pipes are >=2 long), so CONTROL's top wall cannot sit at
row 18 or 19; it starts at row 20. 841 x 4923 = 4.14M, which does NOT beat the
champion's 3,963,967. 28x28 = 784 is required, and needs one row removed from
MEM or from CONTROL:

 (a) MEM 18 -> 17 rows: drop ring8 to nrelay=7 (dn=8, upn=6 makes m_on_up true,
     so bot = top+2+dn = 15 instead of 16) and move the return run to row 15,
     west of ring8's cols 12-13. Costs ticks: lap 20/7 = 2.857 t/relay vs
     22/8 = 2.75, about +6 t/op, landing ~784 x 5044 = 3.95M. Beats the
     champion by only 0.3% -- too thin to rely on.
 (b) CONTROL 9 -> 8 rows (6x6 interior): 19 ops + ~7 turns = 26 cells in 36, so
     it FITS by area, but I could not route it. Both branch arms must return to
     the row-1 loop turn, and they cannot share col 1: the read arm's col-1
     cells are '0','s','0','s', so a write man merging into them would send 0
     instead of 1. Every variant either walks into a wall at (2,1) above the
     '@', or makes (2,1) a turn and forms a two-cell infinite loop with (1,1).

 (c) BEST -- change the protocol so the arms get shorter, which fixes (b) AND
     saves ticks. Send op BEFORE value, and omit value entirely on reads:
        CONTROL: ... s(delta), then branch:  write -> 1, s, r, s
                                             read  -> 0, s
        MEM tap: r(op), X;  read arm r(belt), S
                            write arm r(value), M, r(belt), W, s
     Arms drop from 8 ops to 6, which is what makes a 6x6 CONTROL routable, and
     every READ op now carries 2 values instead of 3 -- fewer sends in CONTROL
     and one fewer read in MEM, so ticks IMPROVE rather than regress like (a).
     This is a protocol change: re-run the 34-case fuzz, not just the 7 public.

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

*** DUAL-PUMP: DONE, AND THE RECEIVED WISDOM ABOUT IT WAS WRONG. ***
The note this replaces said "1 man = 0.500 val/tick, 2 men = 1.000, 3 men
worse".  Those numbers come from an isolated rig with an unconstrained source
and sink.  In a CLOSED TWO-STATION BELT they do not hold, and building to them
costs you the program:

  * NEVER PUT TWO MEN IN ONE RING.  Pipe contention is strict ascending-man-id.
    Whenever both men are parked on `r` for the same pipe the OLDER one takes
    every value -- relays, walks on, blocks, wins again -- and the younger
    never moves at all.  The older then laps the ring and walks into him, and
    "a mover entering a blocked man's cell halts BOTH" (docs/multi-man-
    interactions.md 4b).  Non-fatal, silent, and terminal: a shared 14x5 HOP
    ring lost both men inside a few thousand ticks and every multi-op case
    timed out with EMPTY OUTPUT (not a wrong answer -- a stall).
    This is not tunable.  Whichever station is not the belt's bottleneck is
    starved by definition, and priority-by-id makes that starvation one-sided.

  * TWO MEN, TWO SEPARATE RINGS.  Rings that share no cells cannot collide, so
    a starved man merely parks (free and indefinite) and the pair degrades
    gracefully to one man.  That is what both stations do now.

  * WHO MAY BE MULTI-MANNED.  The 100 values queue immediately upstream of the
    SLOWEST station, so the bottleneck station's input is always full and its
    output always drained -- it is the one station that never blocks.  Keep MEM
    the bottleneck (0.571 val/tick) and HOP comfortably faster (~0.85) and MEM's
    men never block on either side.

  * BELT FIFO SAFETY.  Two men invert order only when both are blocked holding
    values (again ascending-id, not receive order).  Keeping |p2| > 100 keeps
    the standing queue off p2's source cell, so HOP's `s` never blocks; keeping
    HOP faster than MEM keeps p1 drained, so MEM's `s` never blocks.

  * Birth cells must be non-blank -- a copy executes its birth cell while still
    carrying the parent's heading, so a blank one walks it into a wall.

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
# OUT and CMD are SWAPPED relative to the obvious order, to keep the layout
# PLANAR. CONTROL sits north-east of MEM, so a cmd pipe attaching at the far
# west has to cross p1 (x=14) and p2 (x=9) on its way there, and every row is
# already taken (18-23 by p1's descent, 24-25 by HOP, 26-31 by the serpentine).
# Putting CMD at x=1 lets cmd run down the far-west column with nothing to
# cross. CMD cannot instead move EAST: every command-read must be nearer CMD
# than P2 while the belt-reads stay nearer P2, so CMD is pinned west of them.
X_OUT, X_CMD, X_P2, X_P1 = 3, 1, 9, 14
MEM_W, MEM_H = 22, 18          # room(0,0,MEM_W,MEM_H) -> interior 1..20 x 1..16
# 17 -> 22 wide purely to host the HELPER pump ring (cols 18/19) and its `H`
# at col 20.  Free: the box is height-driven (42) and the belt serpentine
# already reaches col 31, so MEM's extra columns cost nothing.  Binding still
# holds there -- an `s` at col 18/19 is 4-5 from P1(14) vs 15-16 from OUT(3),
# and an `r` is 9-10 from P2(9) vs 17-18 from CMD(1).
MEM_BOT = MEM_H - 1            # bottom wall row 17
PIPE_ROW = MEM_H               # attachment cells sit on row 18


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


def vring_mirror(P, down, up, top, nrelay):
    """East-facing mirror image of `vring`, for the HELPER pump ring.

    The man arrives EASTBOUND on row `top`; `up` == down+1 sits to the EAST.
    Every horizontal glyph and every BP-conditional turn is mirrored:

        (down, top)   'd'  guard : BP>0 -> cw(east->south) into the ring
                                   BP==0 -> straight east onto the exit cell
        (up,   top)   '>'  exit  : ring-exit (from the north) and guard-bypass
                                   (from the east) MERGE here, both heading east
        (up, top+1)   'a'        : BP>0 -> ccw(north->west) back to the entry

    So the helper leaves the ring heading EAST, into the `H` that retires it,
    while `vring` leaves heading WEST toward the tap.  Same relay count and
    the same lap length, so the two men do identical work.
    """
    dn = 2 * ((nrelay + 1) // 2)
    upn = 2 * nrelay - dn
    m_on_up = (dn - upn) >= 1
    bot = top + (2 if m_on_up else 3) + dn
    P(down, top, 'd')
    P(down, top + 1, 'v')
    off = top + 2
    if not m_on_up:
        P(down, top + 2, 'm')
        off = top + 3
    for i in range(dn):
        P(down, off + i, 'rs'[i % 2])
    P(down, bot, '>')
    P(up, bot, '^')
    for i in range(upn):
        P(up, bot - 1 - i, 'rs'[i % 2])
    for y in range(top + 2, bot - upn):
        P(up, y, ' ')
    if m_on_up:
        P(up, top + 2, 'm')
    P(up, top + 1, 'a')
    P(up, top, '>')
    return bot


def relay_run(P, cells):
    """Fill a run of cells (in TRAVEL order) with `r`/`s` pairs.

    Every `r` must be IMMEDIATELY followed by its `s`, so a run of odd length
    gives up its LAST cell to a blank rather than stranding a lone `r` across
    a turn (which would let a second value be received before the first is
    sent, and that is precisely how belt order gets silently inverted).
    """
    n = len(cells) // 2 * 2
    for i, (x, y) in enumerate(cells):
        P(x, y, 'rs'[i % 2] if i < n else ' ')


def hop(p, P, HX, HY, W, C):
    """The belt's p1->p2 relay station, pumped by two men in TWO SEPARATE rings.

    *** WHY NOT TWO MEN IN ONE RING.  Measured, and it is fatal. ***
    Pipe contention is strict ascending-man-id, so whenever both men are
    parked on `r` waiting for the same pipe the OLDER one takes every single
    value: it relays, walks on, blocks again, wins again.  The younger man
    never moves.  The older therefore laps the ring and walks into him -- and
    "a mover entering a blocked man's cell halts BOTH" (docs/multi-man-
    interactions.md 4b), non-fatally and silently.  A build with one shared
    14x5 ring lost both HOP men within a few thousand ticks and every case
    timed out with empty output.  This is not tunable: any station that is
    not the belt's bottleneck is starved by definition, so its ring WILL
    stall, and priority-by-id makes the stall one-sided.

    Two independent rings share no cells, so they can never collide.  A
    starved man simply parks (free and indefinite) and the other keeps
    working -- the pair degrades gracefully to one man instead of dying.

        row 1   >  r s r s r s r s r s r s r s r s r s  v     ring A, east
        row 2   ^  s r s r s r s r s < s r s r s r s r  <              west
        row 3   .  @ . . . . . . . Y . . . . . . . . .  .     spawn, used ONCE
        row 4   >  r s r s r s r s > r s r s r s r s .  v     ring B, east
        row 5   ^  s r s r s r s r s r s r s r s r s r  <              west

    A room may hold AT MOST ONE `@`, so man two has to come from `Y`.  `Y`
    births right and left of the parent's HEADING: an east-facing parent
    births NORTH and SOUTH, which is why the spawn lane sits between the two
    rings -- (C,2) lands in ring A and (C,4) in ring B.

    BIRTH CELLS MUST NOT BE BLANK.  A copy executes its birth cell on its
    first tick while still carrying the parent's heading, so (C,2) holds `<`
    (ring A's row 2 runs west) and (C,4) holds `>` (ring B's row 4 runs
    east); blanks there would march both copies straight on into a wall.
    Both glyphs are no-ops for the men that later stream through them.

    Nothing re-enters row 3, so the `Y` cannot re-fire; a `Y` left ON a ring
    would double the population every lap.

    Each ring is 2W cells with ~W-3 relays, so the pair sustains ~(W-3)/W
    values/tick: 0.85 at W=20 against the 0.35 of the old single-man 12x4
    room.  That is what lets MEM's twin rings (0.571) be the bottleneck,
    which in turn is what keeps MEM's two men from ever blocking.
    """
    H = lambda x, y, c: P(HX + x, HY + y, c)
    p.room(HX, HY, W + 2, 7)
    for ry in (1, 4):                    # two 2-row rings, rows 1-2 and 4-5
        H(1, ry, '>'); H(W, ry, 'v')
        H(W, ry + 1, '<'); H(1, ry + 1, '^')
    # spawn lane (row 3), walked exactly once
    for x in range(1, W + 1):
        H(x, 3, ' ')
    H(2, 3, '@'); H(C, 3, 'Y')
    H(C, 2, '<'); H(C, 4, '>')           # birth cells -- never blank
    # relays, in TRAVEL order, split around each birth cell so no r/s pair
    # straddles it or a corner turn
    R = lambda cells: relay_run(P, [(HX + x, HY + y) for x, y in cells])
    R([(x, 1) for x in range(2, W)])                     # ring A row 1, east
    R([(x, 2) for x in range(W - 1, C, -1)])             # ring A row 2, west
    R([(x, 2) for x in range(C - 1, 1, -1)])
    R([(x, 4) for x in range(2, C)])                     # ring B row 4, east
    R([(x, 4) for x in range(C + 1, W)])
    R([(x, 5) for x in range(W - 1, 1, -1)])             # ring B row 5, west
    # relays, split by the fork cell so no pair straddles it


def build():
    p = Program()
    P = p.put

    # ================= MEMORY : cols 0-18, rows 0-20 =================
    p.room(0, 0, MEM_W, MEM_H)

    # -- init: A=20, BP=20, A=0, then 20 laps x 5 sends of 0 = 100 zeros --
    # 5 sends/lap (not 10) keeps every init 's' at x>=8, which is what binds
    # them to the belt rather than the output pipe (OUT/P1 midpoint is 7.5).
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
    # r:A=delta  M:B=delta  `100`:A=100  W:A=delta,B=100  %:A=rot
    # M:B=rot  8:A=8  W:A=rot,B=8  /:A=a,B=r8
    P(1, 4, '>')
    for i, c in enumerate("rM`100`W%M8W/"):
        P(2 + i, 4, c)
    P(15, 4, 'b')                          # BP = a  (hoisted off row 5: BOTH
    P(16, 4, 'v')                          # copies must inherit the lap count)

    # -- row 5: the two rings, flowing WESTWARD --
    # THE FORK.  The man arrives southbound on (16,4)->(16,5)='Y' carrying
    # A=a, B=r8, BP=a.  `Y` births right and left OF THE HEADING, so a
    # south-facing parent births WEST and EAST:
    #   (15,5) west  = the RIGHT copy, which KEEPS THE CREATION ORDER (low id)
    #                  -> the MAIN man, walks west into the counted ring
    #   (17,5) east  = the LEFT copy, newest (high id) -> the HELPER
    # Giving the main man the low id is deliberate: pipe contention is
    # ascending-id, so the main man never loses a tick to the helper.  The
    # helper losing one is self-correcting -- a one-tick stall shifts its ring
    # out of phase with the main ring's `r` cells, after which they stop
    # contending at all.
    #
    # BOTH BIRTH CELLS ARE TURNS.  A copy executes its birth cell on tick one
    # while still heading SOUTH; blanks would march both into row 6.
    P(16, 5, 'Y')
    P(15, 5, '<')                          # main copy -> west
    P(14, 5, ' ')
    P(17, 5, '>')                          # helper copy -> east
    # Two men, TWO SEPARATE RINGS -- never one shared ring.  Sharing is fatal:
    # under contention the older man wins every value, the younger never
    # moves, and the older laps around and rams him, which halts BOTH men
    # silently (see the hop() docstring; a shared-ring HOP died exactly so).
    # Separate rings share no cells, so the worst case is a stalled helper.
    #
    # Each ring relays 4 values per 14-tick lap, so the PAIR does 8 relays per
    # lap -- the same 8-per-`a` the `M8W/` split above already assumes, so the
    # rotation arithmetic is untouched (a = rot>>3, r8 = rot&7).  Cost falls
    # from 22 ticks per 8 relays (2.75 t/value) to 14 (1.75 t/value).
    #
    # THE HELPER MUST FINISH BEFORE THE MAIN MAN TAPS, or the tap reads a
    # half-rotated belt -- silently, never as a crash.  Two guarantees: the
    # rings are identical so the men do identical work, and the main man still
    # has ~16 ticks of exit corridor (W, b, ring1, the row-5 run, the tap's
    # own cmd/op reads) before it touches the belt.
    vring(P, 13, 12, 5, 4)                 # MAIN   ring: 4 relays / 14-cell lap
    vring_mirror(P, 18, 19, 5, 4)          # HELPER ring: identical, exits east
    P(20, 5, 'H')                          # ...into retirement; halted men are
                                           # reaped, so they leave no obstacle
    P(11, 5, 'W')                          # A = r8 (B survived the relays)
    P(10, 5, 'b')                          # BP = r8
    vring(P, 9, 8, 5, 1)                   # remainder ring: 1 relay / 8-cell lap
    for x in range(5, 8):
        P(x, 5, ' ')
    P(4, 5, 'v')

    # -- tap: read the command pair, dispatch on op --
    # Command reads sit at col 4, not col 5: with CMD=1 and P2=9 the midpoint is
    # x=5, so a read at col 5 TIES and would rely on reading order to bind.
    P(4, 6, 'r')                           # second value (CMD 3 vs P2 5)
    P(4, 7, 'M')                           # B = value
    P(4, 8, 'r')                           # op           (CMD 3 vs P2 5)
    P(4, 9, 'X')                           # op=1 -> cw(south->west); op=0 -> south
    # READ arm (op == 0): tap the belt, output AND reinject
    P(4, 10, '>'); P(5, 10, ' '); P(6, 10, ' ')
    P(7, 10, 'r')                          # belt value   (P2 2 vs CMD 6)
    P(8, 10, 'S')                          # -> output pipe AND belt (reinject)
    P(9, 10, ' '); P(10, 10, ' '); P(11, 10, 'v')
    for y in range(11, 16):
        P(11, y, ' ')
    P(11, 16, '<')
    # WRITE arm (op == 1): discard the old belt value, send the new one
    P(3, 9, 'v')
    for y in range(10, 14):
        P(3, y, ' ')
    P(3, 14, '>'); P(4, 14, ' '); P(5, 14, ' '); P(6, 14, ' ')
    P(7, 14, 'r')                          # old value, discarded
    P(8, 14, 'W')                          # A = value (from B)
    P(9, 14, 's')                          # -> belt      (P1 5 vs OUT 8)
    P(10, 14, 'v'); P(10, 15, ' '); P(10, 16, '<')
    # -- return: WEST along row 16, then north up the free col 1 into row 4 --
    for x in range(2, 10):
        P(x, 16, ' ')
    P(1, 16, '^')
    for y in range(5, 16):
        P(1, y, ' ')

    # ================= CONTROL : cols 0-9, rows 33-41 =================
    CX, CY = 0, 33
    C = lambda x, y, c: P(CX + x, CY + y, c)
    # 8 WIDE, NOT 10 -- this is a CONNECTIVITY requirement, not an area tweak.
    # In the 27x27 fold CONTROL sits at cols 19-26 rows 18-26; at 10 wide it
    # would start at col 17 and its top-left corner would meet MEM's
    # bottom-right corner diagonally, sealing the right strip off from the
    # bottom-left so the belt serpentine has nowhere to run. At 8 wide, cols
    # 17-18 stay open as a 2-wide channel joining the two regions.
    # Same 19 ops and the same register flow as before, re-laid into a 6x7
    # interior: main line along row 1 and down col 6, prev-update along row 7,
    # then the op branch.
    p.room(CX, CY, 8, 9)
    for i, c in enumerate(">@rbrv"):       # >=loop-back turn, @, op, BP=op, addr
        C(1 + i, 1, c)
    for i, c in enumerate("-s+M1<"):       # A=delta, send it, A=addr, B=addr, A=1
        C(6, 2 + i, c)
    C(5, 7, '+'); C(4, 7, 'M')             # prev := addr+1 (the tap's reinject
    C(3, 7, 'd')                           #  advances the belt one extra step)
    # WRITE arm (BP=op>0 -> cw from west = north): value, then the op literal 1
    C(3, 6, 'r'); C(3, 5, 's'); C(3, 4, '1'); C(3, 3, 's'); C(3, 2, '<')
    C(2, 2, '<')
    # READ arm (BP==0 -> straight west): 0, then 0. Both arms return up col 1.
    C(2, 7, '0'); C(1, 7, '^')
    C(1, 6, 's'); C(1, 5, '0'); C(1, 4, 's'); C(1, 3, ' '); C(1, 2, '^')
    for y in range(3, 7):
        C(2, y, ' ')
    for y in range(2, 7):
        C(4, y, ' '); C(5, y, ' ')

    # ================= HOP : cols 20-35, rows 21-25 (TWO men) =========
    hop(p, P, 20, 19, 20, 10)

    # ================= IO =================
    p.output_room(2, 20)                   # follows OUT's new column (x=3)
    p.input_room(10, 33)                   # moved in with CONTROL's new right wall

    # ================= pipes =================
    out = [(X_OUT, PIPE_ROW), (X_OUT, PIPE_ROW + 1)]
    cmd = [(X_CMD, 32), (X_CMD, PIPE_ROW)]
    ipipe = [(9, 34), (8, 34)]             # input left wall -> CONTROL right wall (now col 7)
    p1 = [(X_P1, PIPE_ROW), (X_P1, 22), (19, 22)]   # -> HOP's left wall (20,22)
    # Belt return: serpentine in rows 27-31 over cols 11-31, then north up the
    # deliberately-kept-clear col 10.  The FIRST segment must run SOUTH so the
    # start cell's backward neighbour is (25,25) = HOP's bottom wall; a westward
    # first segment points its backward neighbour at empty space and HOP then
    # has no outgoing pipe at all (fatal no-pipe on its first 's').
    # ...then north up col X_P2, which the serpentine deliberately keeps clear
    # (its horizontal runs start at col 11).
    # BELT LENGTH IS A FIFO-SAFETY PARAMETER, not just latency.  Two rules:
    #  (a) THROUGHPUT CEILING.  100 values live in a loop of L = |p1| + |p2|
    #      cells and each advances at most one cell per tick, so a value's
    #      round trip is >= L ticks and (Little's law) the belt can never
    #      sustain more than 100/L values/tick.  A 2-man relay ring demands
    #      ~0.73, so L = 126 (ceiling 0.794) is only 9% clear -- too close.
    #  (b) p2 MUST STAY LONGER THAN 100.  Whichever station is slowest, the
    #      standing queue of ~100 values forms immediately UPSTREAM of it, at
    #      the DESTINATION end of p2.  While |p2| > 100 that queue cannot
    #      reach p2's SOURCE cell, so HOP's `s` never blocks -- which is what
    #      keeps a multi-man HOP FIFO-correct.  (Two men only invert order
    #      when both are blocked holding values, because contention is by
    #      ascending man id, not by who received first.)  Shrinking p2 below
    #      ~104 would silently reorder the belt.
    # So: p2 105, p1 11 -> L = 116, ceiling 0.862 val/tick, p2 slack ~9 cells.
    p2 = [(25, 26), (25, 27), (11, 27), (11, 28), (31, 28), (31, 29),
          (11, 29), (11, 30), (26, 30), (26, 31), (X_P2, 31),
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
