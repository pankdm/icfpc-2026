"""Reusable littleman builders discovered while solving `reverse-a-list`.

Import pattern (from repo root):
    import sys; sys.path.insert(0, 'tools'); import littleman as lm
    sys.path.insert(0, 'solutions/reverse-a-list'); import dsl

These are candidates for promotion into tools/littleman.py's PATTERNS section
(do NOT edit littleman.py directly per task rules). See the report at the bottom.

--------------------------------------------------------------------------------
MECHANISM (reverse-a-list) — how a FIFO-only machine reverses a list
--------------------------------------------------------------------------------
littleman pipes are FIFO and a pipe may not loop back to its own room, so the
only storage is a two-room ring: CTRL --FEED--> PUMP --RETURN--> CTRL, where PUMP
is a dumb forwarder looping `R ; s` (receive-any, send). That ring behaves as a
single FIFO queue for CTRL: `s` enqueues (nearest outgoing = FEED), `r` dequeues
(nearest incoming = RETURN). `r` blocks until the oldest value arrives, so pipe
latency needs no explicit handling.

Reversal is by rotation (O(n^2) ops, fine for n<=16). To emit m elements in
reverse: BP=m; loop { deq -> if BP-->0 re-enqueue else output }. Each outer pass
rotates the queue so the LAST-enqueued element reaches the front and is output,
shrinking the queue by one. Register dance keeps the running size m in B.

Nearest-pipe control (verified against the oracle): `s` picks the nearest
OUTGOING pipe, `r` the nearest INCOMING pipe (Manhattan distance to the pipe cell
adjacent to the room; reading-order tie-break). So FEED(out)+RETURN(in) may share
a wall, and I(in)+O(out) may share a wall; only out-vs-out (FEED/O) and in-vs-in
(I/RETURN) must be separated. Place each pipe-op cell nearer its target pipe than
the competitor. Blank interior cells are valid no-ops (walk straight through), so
only turns and instructions need placing.

The ring must physically hold all n values at once during READ, so
len(FEED)+len(RETURN)+pump >= n (=16). Keep RETURN >= ~17 cells.

Multiple rounds: after emitting, the CTRL man loops back to the count-read `r`,
which blocks until the next round's input is released (input is gated on output).
No reset needed; registers are re-initialised by the fresh count read.

--------------------------------------------------------------------------------
FOOTPRINT KEY INSIGHT (ring-v2, 20x20 box400 @ ~2390 ticks, submit score 1,536,640
vs the old 24x25 box625 @ ~2424, submit 2,452,937 -- a 37% score cut):
--------------------------------------------------------------------------------
The nearest-pipe decision for every `s`/`r`/`q` depends ONLY on each pipe's
ATTACHMENT CELL (the pipe segment adjacent to the CTRL wall), never on where the
satellite room sits or how the pipe is routed afterwards. So you can keep a
working CTRL's internals 100% unchanged and freely RELOCATE the I/O/PUMP rooms and
RE-ROUTE their pipes to shrink the bounding box, as long as each pipe still
attaches at the same CTRL cell. Wins that dropped v3's 625 -> 400 (see
`ringp.build`, parametric on the read-racetrack send row RB):
  * INPUT on the RIGHT wall instead of the top. read-r cells (upper-centre) stay
    nearest to I while deq-r (lower-left) stays nearest to RETURN, so semantics
    hold -- and the whole top stack (room+pipe, ~5 rows) disappears.
  * I and O rooms hung COMPACTLY off the right in cols25-27 via short vertical
    pipes (right margin 3 not 5).
  * RETURN folded to a narrow left margin; ring capacity must stay >= n_max=16
    (len(FEED)+len(RETURN)+pump(=1) >= 16), which is the real floor on ring size.
Bottleneck now: CTRL is 15w x 14h fully used; both bbox dims are 20 (CTRL + 6-row
FEED/PUMP stack below + minimal side margins). Going below 400 needs the CTRL
itself repacked smaller (RB=4 collides: OUT-return row == SETUP turn row).
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools"))
import littleman as lm


def pipelen(pts):
    """Number of cells in a pipe routed through orthogonal waypoints `pts`."""
    n = 0
    for i in range(len(pts) - 1):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        n += abs(x1 - x0) + abs(y1 - y0)
    return n + 1


def pump_forwarder(p, x, y, w, right_col):
    """Place a 2-row 'pump' man that loops `R ; s` (receive-any -> send nearest out),
    turning a CTRL->PUMP + PUMP->CTRL pipe pair into a single FIFO queue for CTRL.
    Room interior is rows y+1..y+2, cols x+1..x+w-2; `right_col` is the interior
    right column used for the racetrack turn."""
    r1, r2 = y + 1, y + 2
    p.put(x + 1, r1, ">"); p.put(x + 2, r1, "@"); p.put(x + 3, r1, "R"); p.put(x + 4, r1, "s")
    p.put(right_col, r1, "v"); p.put(right_col, r2, "<"); p.put(x + 1, r2, "^")
    return p


def build_reverse():
    """Return the best reverse-a-list Program (footprint 24x25, box 625).

    Layout (CTRL interior cols 11..23):
      I    top    col17     (count + value reads)
      FEED bottom col17     (enqueue)
      RETURN left row Orow  (dequeue)          } ring via PUMP below
      O    right row Orow   (output)
    CTRL man program (only meaningful cells placed; blanks are no-ops):
      SETUP     read n, B=n, BP=n
      READ loop racetrack: read value (top) -> enqueue (bottom) -> BP-- -> branch
      EOUTER    W;X  (A=m; if m==0 loop to SETUP for next round, else rotate)
      DOROT     b M 1 W - M   (BP=m, B=m-1)
      DEQ loop  r ; m ; a-branch: BP>0 -> ENQ(s) -> loop ; BP==0 -> OUT(s,output)
    """
    RB = 5                       # read racetrack bottom row
    EO = RB + 1                  # EOUTER row
    p = lm.Program()
    BOTROW = EO + 6
    HT = BOTROW + 1              # CTRL interior rows 1..HT
    p.room(10, 0, 15, HT + 1)                                   # CTRL
    p.input_room(16, -5); p.pipe([(17, -2), (17, -1)])          # I top col17
    Orow = EO + 2
    p.output_room(27, Orow - 1); p.pipe([(25, Orow), (26, Orow)])  # O right
    py = HT + 3
    p.room(10, py, 15, 4)                                       # PUMP below
    p.pipe([(17, y) for y in range(HT + 1, py)])                # FEED CTRL->PUMP
    ret = [(9, py + 2), (6, py + 2), (6, Orow), (9, Orow)]       # RETURN PUMP->CTRL (len>=17)
    p.pipe(ret)
    pump_forwarder(p, 10, py, 15, 23)
    P = p.put
    # SETUP
    P(12, 1, "@"); P(14, 1, ">"); P(17, 1, "r"); P(18, 1, "M"); P(19, 1, "b"); P(20, 1, "v"); P(20, 3, "<"); P(15, 3, "^")
    # READ racetrack (bottom = RB)
    P(15, 2, ">"); P(17, 2, "r"); P(19, 2, "v"); P(19, RB, "<"); P(17, RB, "s"); P(16, RB, "m"); P(15, RB, "d")
    # READ-exit -> EOUTER
    P(11, RB, "v"); P(11, EO, ">"); P(12, EO, "W"); P(13, EO, "X"); P(14, EO, "^")
    # DOROT
    dr = EO + 5
    P(13, dr, ">"); P(14, dr, "b"); P(15, dr, "M"); P(16, dr, "1"); P(17, dr, "W"); P(18, dr, "-"); P(19, dr, "M")
    P(20, dr, "^"); P(20, EO + 1, "<")
    # DEQ
    P(11, EO + 1, "v"); P(11, EO + 2, "r"); P(11, EO + 3, "m"); P(11, EO + 4, "a")
    # ENQ
    P(12, EO + 4, ">"); P(17, EO + 4, "s"); P(19, EO + 4, "^"); P(19, EO + 1, "<")
    # OUT
    P(11, EO + 6, ">"); P(23, EO + 6, "^"); P(23, Orow, "s"); P(23, RB - 1, "<"); P(11, RB - 1, "v")
    return p


if __name__ == "__main__":
    p = build_reverse()
    print(p.render())
    print("footprint:", p.footprint())
    print("grade:", p.grade("reverse-a-list"))
