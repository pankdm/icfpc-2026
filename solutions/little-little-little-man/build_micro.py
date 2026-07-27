#!/usr/bin/env python3
"""LLLM micro-design: a hand-structured LANE layout for the LLLM interpreter.

STATUS: FLOORPLAN + GEOMETRY ONLY.  `build()` is not written yet; everything
below is the contract the emitter has to satisfy.  Run this file to print the
lane windows and the box budget.

WHY THIS FILE EXISTS
  The champion (polish-203x200.man) is 203x200 = box 41,209 at 16.1% density and
  493,360 avgTicks -> server 22,459,642,837.  The leader is 1,178,367,086.
  Ticks required to reach the leader, by box:
      box 41,209 (203x203) ->  28,595 ticks   (17.3x faster than now)
      box 10,000 (100x100) -> 117,837         ( 4.2x)
      box  9,216 ( 96x 96) -> 127,861         ( 3.9x)
      box  2,500 ( 50x 50) -> 471,347         ( 1.05x)
  LLLM needs BOX, not ticks.  build_lllm.py already reaches 197,143 avgTicks in
  117x391 (box 152,881) using only 4,128 content cells; the content is right and
  the layout is wrong.  This file is the layout.

  The compiled-CFG boustrophedon ribbon cannot be folded -- nine levers were
  measured dead, see docs/boustrophedon-layout-limits.md.  Snake hit the same
  wall and escaped by ABANDONING the compiled CFG for a hand-structured lane
  layout (170x253 -> 91x94, box 64,009 -> 8,836, 113x on score).  This is the
  same move.

CALIBRATION (measured, 2026-07-26)
  solutions/snake/micro4.man   91x94, 1,080 content cells total.
  Its controller interior (58 columns x 77 rows) holds 517 op cells = 6.7 per
  row.  That density is what a lane layout costs when the lanes are ~13 columns
  wide and the blocks are short.  Two levers move it here:
    * 3+3 controller pipes on a 64-column interior give ~21-column lanes, so a
      `r:S s:S` pair costs 2 cells and TEN pairs fit on one row (snake: seven);
    * straight-line arithmetic runs bind no lane at all and pack at 1 cell per
      column, i.e. 64 per row.  Table lookups therefore beat branch trees for
      BOX even when they cost more ticks -- a branch costs ROWS (arm, branch,
      arm, plus a highway column), a `*`/`}`/`&` costs one cell.
  Governing law (docs/boustrophedon-layout-limits.md): rows ~ blocks + wraps.
  Minimise the number of BRANCH TARGETS, not the number of ops.

  TICKS ARE ALREADY WON.  Public workload: 10 cases, 1,033 program cells, 116
  rounds, sum(k) = 585, max k = 64, cap 15,000,000.  That is ~103 program cells
  and ~58 LLLM ticks per case.  Anything at or under 197,143 avgTicks wins at
  box 9,216.  So SPEND TICKS TO BUY ROWS: loop instead of unrolling, recompute
  instead of caching, take an extra ring lap instead of adding a slot.

════════════════════════════════════════════════════════════════════════════
ARCHITECTURE
════════════════════════════════════════════════════════════════════════════

  STATE RING   a FIFO ring of 14 scalars in ONE canonical order, popped and
               pushed once per phase (`r:S s:S` leaves A intact and the ring
               rotated by one, so a lap is order-preserving).  Order matches
               the per-tick access sequence exactly:

                 0  halted     0 / 1
                 1  k          ticks left in this round
                 2  x          man column 0..15
                 3  C_cur      colour plane word for row y  (nibble of column
                               c at bits 4*(15-c); values 0,3,4,8,10,12)
                 4  V_cur      value plane word for row y
                 5  A_lm       the LLLM A register (i64, wrapping)
                 6  B_lm       the LLLM B register
                 7  dx         -1 / 0 / +1
                 8  dy         -1 / 0 / +1
                 9  y          man row 0..15
                10  cur_col    static colour of the cell the man stands on
                11  prev_addr  display address painted last frame
                12  prev_col   static colour of that cell
                13  ret        return code for the shared services

               Temps are PARKED PAST THE LIVE COUNT (push at the tail, recover
               one lap later) instead of getting their own slot -- deleting one
               slot is cheaper than deleting one op, and deleting a whole RING
               is what buys the lane width (snake finding 6).
               During LOAD the same 14 slots are ALIASED onto the loader's
               scalars (W, H, cx, cy, rowC, rowV, x0, y0, x1, y1, atx, aty,
               ...); no step scalar is live before RENDER_DONE.

  PROG RING    the program, as TWO 4-BIT PLANES, one i64 per LLLM row:
               C[y] (colour/opcode) and V[y] (operand).  The ring holds the 15
               rows OTHER than the man's, in cyclic row order, head = row y+1;
               the man's own row lives in the state ring as C_cur/V_cur.  30
               slots.  Addressing row y is POSITIONAL -- there is no decode and
               no branch:
                 dy = 0   nothing at all (horizontal moves are FREE)
                 dy = +1  s:P C_cur, s:P V_cur, r:P C_cur, r:P V_cur   (O(1))
                 dy = -1  the same, then a 14-row rotation = 28 `r:P s:P`
                          pairs run as a `b`/`d`/`m` COUNTED LOOP: ~12 grid
                          cells, ~150 ticks.  Ticks are free; rows are not.

               *** THIS REPLACES THE "16 REPEATER ROOMS" IN THE BRIEF, AND THE
               REASON IS THE LANE ARITHMETIC. ***  16 repeater rooms exposing
               OP[y] and VAL[y] would be 32 incoming pipes.  Lane width =
               interior width / number of pipes in that DIRECTION, so 32
               incoming ports on a 64-column interior gives 2-column lanes.
               Snake measured 4 in-pipes on a 34-wide room -> 5-column lane ->
               half a row per r/s pair; 2-column lanes mean essentially EVERY
               `r` wraps, i.e. >= 1 row per program-plane read, and the step
               loop reads twice per tick.  It also needs a 16-way branch to
               choose the column (16 more blocks) and 16 rooms + 32 pipes in
               the band (width blows past 96).  The ring keeps the property the
               brief actually wanted -- O(1) access with no lap per access --
               and costs TWO pipes instead of thirty-two.

  DRIVER       owns the display's ADDR/DATA/SWAP pipes and exposes ONE incoming
               pipe (snake finding 3: three lanes collapse into one).
                    v >= 0  -> ADDR := v, then the NEXT value -> DATA
                    v == -1 -> SWAP 1   (commit, PRESERVING next + cursor,
                                         which is what makes delta frames legal)
               ~25 grid cells; reuse snake's driver block verbatim.

  CLASSIFIER   BRANCHLESS.  h(c) = ((c * 29) >> 6) & 15 is injective over all
               twelve non-digit characters that can appear:
                 ' '14  '+'3  '-'4  '<'11  '>'12  '@'13
                 'H'0   'M'2  'X'7  '^'10  'v'5   '|'8
               Two packed i64 tables, both inline backtick literals:
                 COLW = 900500832300035     (15 digits, reverses to 530003238005009)
                 VALW = 1760322152103950    (16 digits, reverses to 593012512230671)
               both fit i64 read in either direction.
                 colour = (COLW >> (4*h)) & 15
                 val    = (VALW >> (4*h)) & 15
               Digits are folded in BRANCHLESSLY (a branch costs rows):
                 t  = c - 48
                 m  = (t - 10) } 63        -1 iff t < 10
                 m2 = t } 63               -1 iff t < 0
                 isdig = m & ~m2           -1 or 0
                 colour = (8 & isdig) | (colour & ~isdig)
                 val    = (t & isdig) | (val    & ~isdig)
               ~90 straight-line cells = under TWO ROWS, and ZERO blocks.  The
               ternary `X` tree it replaces is 13 leaves = 13 blocks ~ 40 rows.

  VAL ENCODING chosen so that no direction decode ever branches.  For the six
               colour-3 characters V packs the step as V = 4*(dy+1) + (dx+1):
                 '^' 1   '>' 6   'v' 9   '<' 4      'X' 15   'H' 14
               so an arrow executes as   dx = (V & 3) - 1 ;  dy = (V >> 2) - 1
               in ~10 straight-line cells.  `dir` is therefore NOT a ring slot,
               and the 4-arm heading decode (4 blocks) disappears.  X rotates
               (dx,dy) directly: CW (dx,dy)->(-dy,dx), CCW (dx,dy)->(dy,-dx).

  WALLS        resolved POSITIONALLY during the load scan, never by character
               (public case 'swan dive' has a real '+' and '-' INSIDE the room;
               colouring by character passes 9/10 public and fails privately):
                 (x0,y0) = the FIRST '+' in reading order
                 x1      = the next '+' on row y0
                 y1      = the first '+' in column x0 with y > y0
               After the scan, ONE lap of the PROG ring overlays colour 4:
                 rows y0 and y1 : nibbles x0..x1 := 4
                 rows in between: nibbles x0 and x1 := 4
               The two patterns and the keep-mask are built once, arithmetically:
                 span = ((1 << 4*(x1-x0+1)) - 1)          (`{` then -1)
                 full = span / 15 * 4                     (`/` gives 0x444..4)
                 keep = ~(span << 4*(15-x1))              (`~` with B = -1)
                 side = (4 << 4*(15-x0)) | (4 << 4*(15-x1))
               ~80 cells, then a 16-iteration overlay loop of ~40.

════════════════════════════════════════════════════════════════════════════
BINDING -- why there are exactly SIX controller pipes
════════════════════════════════════════════════════════════════════════════
`s`/`r` pick the NEAREST attached pipe (Manhattan to the pipe's first/last cell,
ties in reading order).  EVERY controller pipe attaches to the TOP wall, so the
y term is identical for all of them and binding is decided by the COLUMN alone:
the interior splits into vertical LANES and a pipe op may only be emitted inside
its lane's window.  A token that cannot reach its lane on the current row forces
a WRAP -- a whole row.  LANE WIDTH SETS HEIGHT.

`s` consults ONLY the outgoing table and `r` ONLY the incoming one, so the two
are independent -- which is why DRIVER (outgoing only) and INPUT (incoming only)
share the same columns for free.

    outgoing (3):  S_out = 11   ctrl -> state relay
                   P_out = 32   ctrl -> prog relay
                   D_out = 54   ctrl -> driver
    incoming (3):  S_in  = 13   state relay -> ctrl
                   P_in  = 34   prog relay  -> ctrl
                   I_in  = 52   input room  -> ctrl

Ring pairs are always emitted adjacent (`r:S s:S`), so each ring's two ports sit
two columns apart and their windows overlap almost completely.

════════════════════════════════════════════════════════════════════════════
FLOORPLAN                                        width 96, height 96, BOX 9,216
════════════════════════════════════════════════════════════════════════════
  x: 0        11 13     32 34         52 54    65 66 68      76 78          95
  y
   0  +-- STATE relay 10..15 x 0..3 --+  +-- PROG relay 26..31 x 0..3 --+
   1  |  @ > R v / ^ s <              |  (same 8-cell relay block)
   2  |                               |         INPUT room 52..54 x 0..2
   3  +-------------------------------+
   4  |                                                                   |
   5  |   horizontal pipe highways (ring feeds; capacity lives here)       |
   6  |                                                                   |
   7  ATT ROW -- every controller port terminates at (col, 7)
   8  +================ CONTROLLER  x 0..65 (CW=66) ====================+
   9  |                                                                 |    +-- DRIVER 68..76
  ..  |  interior x 1..64  (64 columns)   y 9..94  (86 rows)            |    |   y 10..31
  ..  |                                                                 |    |   +-- DISPLAY
  ..  |                                                                 |    |   |   78..95
  ..  |                                                                 |    |   |   y 12..29
  95  +=================================================================+

  bbox = (0,0)..(95,95)  ->  96 x 96  ->  BOX 9,216
  clearances: controller right wall x=65, driver left wall x=68 (2 blank cols);
              driver right wall x=76, display left wall x=78 (1 blank col, and
              the DATA pipe is the single cell x=77 -- it runs BETWEEN the two
              walls, never ALONGSIDE one, so it steals no bindings).
  ADDR routes over the display top (y=10..11), SWAP under the bottom (y=31..33),
  both inside the driver's row span; nothing below y=33 east of x=66.

  ROW BUDGET for the 86 interior rows (est., blocks + wraps):
      round dispatch / phase select                  4
      LOAD init + PROG-ring zero-fill loop           4
      LOAD cell loop (hash + branchless digit +
        accumulate; 2 branches for '@' and '+')      7
      LOAD row-end (push C,V to PROG ring)           3
      wall-geometry capture (x0,y0,x1,y1)            6
      wall mask build + 16-row overlay lap           6
      initial 256-pixel paint loop                   4
      STEP entry, k loop, halted test                5
      TICK phase 1 (lap: fetch nibbles)              4
      op dispatch tree (colour -> 5 targets)         8
      op arms via the shared STORE service           9
      X turn arms (CW / CCW)                         4
      advance + PROG-ring rotate (2 arms + loop)     7
      wall test on the destination cell              3
      delta frame emit                               4
      return highway / dispatcher chrome             4
      ---------------------------------------------  --
                                                    82   (86 available)

  SHARED SERVICES cut the arm count.  `STORE(n, v)` -- rotate the state ring n
  slots, replace the head, finish the lap -- serves digit (A_lm := V), arrow
  (dx,dy := V), M (B_lm := A_lm), +/- (A_lm := A_lm +/- B_lm) and the advance,
  so each arm collapses to "set n, set v, jump STORE" (~6 cells = 1 row) instead
  of its own 3-row block.  Return is a code in ring slot 13 dispatched at the
  service exit, exactly like snake's `ret_dispatch`.

  FALLBACKS, in order, if the emitter overflows 86 rows:
      1. controller y 8..115  -> 96 x 116 -> box 13,456   (still ~2.0B)
      2. CW 66 -> 76, width 106, interior 74 columns, wider lanes
      3. move DRIVER+DISPLAY to a strip UNDER the controller (width = CW,
         height = 8 + Hc + 24) -- trades 30 columns of width for 24 rows.

════════════════════════════════════════════════════════════════════════════
STEP LOOP, HALT RULES, DELTA FRAMES
════════════════════════════════════════════════════════════════════════════
Round 1:   read W, H, then W*H ASCII -> classify -> pack planes -> capture
           (x0,y0,x1,y1) and the '@' position -> wall overlay -> paint all 256
           pixels -> draw the man (addr, 9) -> SWAP 1 -> prev_addr/prev_col := .
Round n:   read k; loop while k > 0 and not halted:
             1. fetch: sh = 60 - 4*x  (`M + M + N M` then `60` `+`, 10 cells);
                col = (C_cur >> sh) & 15 ;  val = (V_cur >> sh) & 15
                (both extracted with B = sh held across the two `}` -- `r`/`s`
                do not touch B -- and the intermediates PARKED at the ring tail)
             2. execute, dispatching on col:
                   0  space  -- nothing
                   3  arrow class, sub-dispatch on val:
                        0..9 -> dx = (val&3)-1, dy = (val>>2)-1   (branchless)
                        15   -> X: A_lm > 0 CW, < 0 CCW, == 0 straight
                        14   -> H: halted := 1 and DO NOT ADVANCE
                   8  digit  -- A_lm := val
                  10  +/-    -- val 0: A_lm += B_lm ; val 1: A_lm -= B_lm
                  12  M      -- B_lm := A_lm
                   4  wall   -- unreachable (a man on a wall is already halted)
             3. advance (skipped for H): x += dx, y += dy
             4. if dy != 0: swap C_cur/V_cur through the PROG ring (+1 row is
                4 pipe ops; -1 row is that plus a 28-slot counted loop)
             5. WALL HALT: cur_col := (C_cur >> (60-4x)) & 15 ; if cur_col == 4
                then halted := 1.  The man KEEPS the new (x,y) -- he stays ON
                the wall cell and every later frame draws him there.  (This is
                the LLLM rule, the opposite of littleman, where a wall is fatal.)
             6. k -= 1
           then emit the DELTA frame:
                 s:D prev_addr ; s:D prev_col      erase the old man
                 s:D 16*y + x  ; s:D 9             draw the new man
                 s:D -1                            SWAP 1 (preserves the buffer)
                 prev_addr := 16*y + x ; prev_col := cur_col
           Writing both pixels unconditionally is correct even when they
           coincide (k = 0, or halted): the 9 is written second and wins.
           Only TWO pixels ever change, so a frame is 5 sends, not 256.

════════════════════════════════════════════════════════════════════════════
MILESTONE 1 -- complete but deliberately slow; SHIP IT BEFORE OPTIMISING
════════════════════════════════════════════════════════════════════════════
Same rooms, same six pipes, same port columns; only the emitter is dumb.
  * controller allowed to run to y = 115 -> 96 x 116 -> box 13,456
  * classifier as a ternary `X` tree (13 leaves) -- easier to debug; the hash
    tables are a drop-in replacement afterwards
  * no park-at-tail: every scalar access takes a full canonical lap
  * NO delta frames: repaint all 256 pixels every round (deletes prev_addr,
    prev_col and the whole delta path)
  * expected ~400,000 avgTicks -> 13,456 * 400,000 = 5.4e9, i.e. 4.2x better
    than the 22.46e9 champion.  ANY working build in this floorplan beats the
    champion: at 400k ticks the break-even box is 299x299.
  Gate: python3 tools/grade_fast.py little-little-little-man <f>.man --cap 20000000
        must be 10/10 (grade_fast averages over PASSING cases only, so a partial
        pass is NOT comparable), then commit, then submit.
  M2: delta frames + hash classifier + park tricks -> ~57,000 avgTicks.
  M3: fold to 96 rows -> box 9,216 -> ~5.3e8, past the 1.178e9 leader.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "tools"))

# ---- classifier tables (see CLASSIFIER above) ------------------------------
HASH_MUL, HASH_SHIFT = 29, 6            # h(c) = ((c*29) >> 6) & 15, injective
COLW = 900500832300035                  # colour  nibble per hash slot
VALW = 1760322152103950                 # operand nibble per hash slot

# ring sizes
STATE_SLOTS = 14                        # live scalars; temps park past the tail
PROG_SLOTS = 30                         # 15 rows x (C, V); the man's row is in STATE


def geometry(CX0=0, CY0=8, CW=66, CBOT=95,
             S_OUT=11, S_IN=13, P_OUT=32, P_IN=34, I_IN=52, D_OUT=54,
             DRVX=68, DISX=78, DRVY=10, DISY=12):
    """All the integers autotune is allowed to sweep."""
    g = dict(CX0=CX0, CY0=CY0, CW=CW, CBOT=CBOT, DRVX=DRVX, DISX=DISX,
             DRVY=DRVY, DISY=DISY)
    g["CX1"] = CX0 + CW - 1
    g["IXLO"], g["IXHI"] = CX0 + 1, CX0 + CW - 2
    g["IYLO"], g["IYHI"] = CY0 + 1, CBOT - 1
    g["ATT"] = CY0 - 1
    g["attach_out"] = {"S": S_OUT, "P": P_OUT, "D": D_OUT}
    g["attach_in"] = {"S": S_IN, "P": P_IN, "I": I_IN}
    g["W"] = DISX + 18                       # display is 18 wide
    g["H"] = CBOT + 1
    g["BOX"] = max(g["W"], g["H"]) ** 2
    return g


def lane_windows(g):
    """Window for each (op, lane): the columns where that op binds that lane.

    `s` consults only the OUTGOING table and `r` only the INCOMING one, so the
    two are independent -- a receive window may overlap the send window of a
    DIFFERENT lane.  That is why DRIVER (send-only) and INPUT (receive-only)
    can share the whole eastern third.
    """
    win = {}
    for op, table in (("s", g["attach_out"]), ("r", g["attach_in"])):
        for lane in table:
            cols = [x for x in range(g["IXLO"], g["IXHI"] + 1)
                    if min(table, key=lambda k: (abs(table[k] - x), table[k])) == lane]
            best = cur = []
            for x in cols:
                cur = cur + [x] if cur and x == cur[-1] + 1 else [x]
                if len(cur) > len(best):
                    best = cur
            win[(op, lane)] = (best[0], best[-1])
    return win


def report():
    g = geometry()
    win = lane_windows(g)
    print("box %d  (%dx%d)   controller interior %d cols x %d rows"
          % (g["BOX"], g["W"], g["H"], g["IXHI"] - g["IXLO"] + 1,
             g["IYHI"] - g["IYLO"] + 1))
    for key in sorted(win):
        lo, hi = win[key]
        print("   %s:%s  cols %2d..%2d  (%d wide)" % (key[0], key[1], lo, hi, hi - lo + 1))
    for lane in ("S", "P"):
        a, b = win[("r", lane)]
        c, d = win[("s", lane)]
        lo, hi = max(a, c), min(b, d)
        print("   `r:%s s:%s` pairs legal in cols %d..%d -> %d pairs per row"
              % (lane, lane, lo, hi, (hi - lo + 1) // 2))
    a, b = win[("s", "D")]
    c, d = win[("r", "I")]
    print("   `s:D` and `r:I` co-resident in cols %d..%d" % (max(a, c), min(b, d)))


if __name__ == "__main__":
    report()
