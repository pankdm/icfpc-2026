"""memory DUAL-HEAD -- CLOSED A SECOND TIME, now on MEASURED GEOMETRY.

*** DO NOT BUILD THIS.  The two things worth taking are listed first. ***

REUSABLE ARTIFACT 1 -- tools/bindsolve.py (instanced here in
scratchpad/dualhead/bind_solver.py).  Brute-forces a room's pipe ATTACHMENT cells
against every send/receive cell over every wall position and returns the FULL set
of strictly-valid assignments.  Pipe binding has silently broken designs
repeatedly in this repo: `r`/`s` lock onto the NEAREST attached segment (Manhattan,
reading-order ties), so moving a room re-binds instructions with no error and a
7/7 public pass will not catch it.  Stop deriving midpoints by hand -- enumerate.
Here it returned 68 strictly-valid assignments for CONTROL's three pipes against
17 send cells; the two-SEL-send variant returned ZERO, which is how the register
trick below was found rather than guessed at.

REUSABLE ARTIFACT 2 -- THE ONE-SEL-SEND TRICK, a genuine register-wall escape.
MERGE must be told which engine tapped, but ONLY on reads (on a write no engine
sends it anything, so a spurious token deadlocks it).  `which` is only known in
the leaf, where `op` is already dead: A holds the prev computation, B holds prev,
and BP held the selector bit.  The escape is that BP becomes FREE the instant `x`
has consumed its low bit, so each leaf arm does `b` right there to stash op in BP,
and the SHARED tail tests it with `a` -- writes turn away over the SEL send, reads
walk straight through it.  One send, no op token, and the controller keeps 2
leaves instead of 4.  The alternative (send op and which as a pair) has ZERO valid
binding solutions, so this is necessary, not merely neater.  Generalises: a
selector bit consumed by `x`/`d`/`a` frees BP for a second one-bit value inside
the same basic block.

----------------------------------------------------------------------------
WHY IT IS CLOSED.  The score is box x avgTicks, and the box alone decides it:

    dual-head, routed-but-crossing      66 x 55  = 4356
    dual-head, with the fix below       ~73 x ~45 = ~5329
    single-engine lineage (live)        24 x 24  =  576   server 8,290,368

That is 9.3x worse in box against a rotation win of 1.36x on ticks (mean relays
per op 48.46 -> 35.61, validated 7/7 public + 20000 fuzz in
scratchpad/dualhead/proto128.py).  No routing outcome recovers a 9x box.  The
first closure (dualhead_build.py @ 23fafa8) argued this from room-size estimates;
this one measures the actual placed-and-routed geometry.

THE BLOCKER IS FORCED, NOT A ROUTING MISTAKE.  The build places and routes
everything -- both engines, CONTROL, MERGE, both IO rooms, oA, cmdA, SEL, out,
inp, and both belts at 130 and 126 cells (comfortably over the >= 65 floor) --
and then the parser rejects it with

    LoadError: invalid pipe cell '|' at (49, 29)      [trimmed coords]

which is oB crossing cmdB's riser into engine B's CMD column.  The geometric
argument, in order:

  1. All four of an engine's pipes attach to its BOTTOM wall, in the fixed column
     order OX(1) CMD(3) PIN(9) POUT(14).  Those columns ARE the engine's r/s
     bindings (CMD/PIN midpoint 6, OX/POUT midpoint 7.5), so they cannot move.
  2. The belts must therefore wrap OVER the engines.  Routing either belt trunk
     through a gap column instead fences that engine's OX/CMD columns off from the
     controller -- five canvases up to 66x55 were worked through.
  3. Having wrapped, the belts' FULL-WIDTH top runs fence the top channel: every
     column between the two trunks is crossed by p1's row-1 run, so nothing else
     can ascend past them.  That kills the annulus-around-CONTROL escape, which is
     the only way two interleaved chords avoid each other in this floorplan.
  4. What is left is engine B's OX(51) and CMD(53) -- two adjacent columns whose
     risers both need rows 29..30 -- with oB heading for MERGE and cmdB arriving
     from CONTROL.  Their endpoints interleave on the region boundary for EVERY
     placement of MERGE (west, east, under engine B, inside the gap), so the two
     chords must cross.

  INDEPENDENT CONFIRMATION: tools/router.py, a global negotiated-congestion rip-up
  router that had no part in the reasoning above, converges to 1-2 PERMANENTLY
  over-used cells on every one of those canvases and never below.  A hand argument
  and a rip-up router failing at the same place is what makes this credible rather
  than a suspicion that I mis-drew a lane.

WHY THE FIX DOES NOT PAY.  Move OX and CMD off the bottom wall onto the side
walls, leaving only the two belt lanes on the bottom.  With CMD on the LEFT wall
at local row 20 and OX on the RIGHT wall at local row 21 every existing engine op
still binds correctly (checked op by op; tightest margins are 1, all strict):

    r(8,6)  PIN 18 < CMD 23      r(5,9)  CMD 17 < PIN 18
    r(2,4)  CMD 19 < PIN 26      r(5,11) CMD 15 < PIN 16
    r(7,17) PIN  8 < CMD 11      r(5,13) CMD 13 < PIN 14
    s(9,2)  POUT 26 < OX 27      s(9,20) POUT  8 < OX  9

But CMD works ONLY on the left wall: right-wall CMD needs r(5,13) to give
attachment row 12..14 while r(8,6) needs row >= 16, a flat contradiction.  So BOTH
engines take cmd from the west, which forces

    west margin | ENGINE A | CONTROL | ENGINE B | MERGE

with cmdA wrapping over the top to reach engine A's far side -- width ~73, box
~5329, i.e. the fix makes the box WORSE than the crossing version it repairs.
(CONTROL cannot put both cmd pipes on one wall either: with cmdA and cmdB on the
same wall the shared x-term cancels and binding is purely by row, and the two
send-row sets share rows 21 and 23, so no assignment separates them.)

----------------------------------------------------------------------------
What remains below is the floorplan as it stood, kept only so the measurement is
reproducible: hand-routed belts + oA + cmdA + oB + cmdB, and SEL/out/inp left to
tools/router.py.  It emits a 66x55 grid that DOES NOT LOAD, by construction.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
sys.path.insert(0, HERE)

import router                                                  # noqa: E402
from router import Router, UnroutableNet                       # noqa: E402
import dualhead2_build as D                                    # noqa: E402

# route_pipe's default A* window is +-6 cells around the endpoint bbox, which cannot
# see the wrap-around channel above the engines that the belts need.  Widen it.
_orig_route_pipe = router.route_pipe
router.route_pipe = lambda grid, net, extra_cost=None, margin=44: \
    _orig_route_pipe(grid, net, extra_cost=extra_cost, margin=margin)

# ── placement ───────────────────────────────────────────────────────────────
# rows  0.. 5   top channel: BOTH belts wrap over the engines here.  That is the
#               whole floorplan trick -- it keeps the band under CONTROL empty, and
#               that band is the only way cmdA/cmdB/oA/oB/SEL can reach the engines'
#               west pins.  Routing the belts UNDER control instead is what makes the
#               problem non-planar (the belt trunks then fence engine A's OX/CMD
#               columns off from the controller); worked through the hard way.
# rows  6..28   ENGINE A (cols 0..16) | west gap 17..21 | east gap 37..41 | ENGINE B (42..58)
# rows 10..36   CONTROL (cols 22..36)
# rows 29..35   engine fan-out lanes
# rows 40..48   MERGE (cols 22..32) + input room; row 50.. output room
AX, AY = 4, 6                  # engine A     cols  4..20, rows 6..28
CX, CY = 28, 10                # CONTROL      cols 28..42, rows 10..36
BX, BY = 50, 6                 # engine B     cols 50..66, rows 6..28
MX, MY = 42, 42                # MERGE        cols 42..52, rows 42..50 (EAST)
OUTX, OUTY = 46, 53            # output room
INX, INY = 29, 39              # input room (tucked under CONTROL)

# Hand-routed belts (the router MINIMISES length, so it would never wrap over the
# top, and it cannot honour the >= 65-cell floor either).  Waypoints, not cells.
#   p1: A.POUT(14) -> row 30 -> col 17 north -> row 1 east -> col 61 south -> row 34 -> B.PIN(51)
#   p2: B.POUT(56) -> row 33 -> col 60 north -> row 2 west -> col 19 south -> row 31 -> A.PIN(9)
# The east trunks sit EAST OF ENGINE B, not in the gap: a trunk in the gap fences
# engine B's OX/CMD columns off from the controller (the same non-planarity that
# forces the over-the-top wrap on the west side).
# The two never cross: p1 owns the OUTER west trunk (17) and row 1, p2 the inner
# west trunk (19) and row 2, and p1's east legs stay one row above p2's.
P1_PATH = [(18, 29), (18, 30), (21, 30), (21, 1), (69, 1), (69, 34), (59, 34), (59, 29)]
P2_PATH = [(64, 29), (64, 33), (68, 33), (68, 2), (23, 2), (23, 31), (13, 31), (13, 29)]
# oA is hand-routed too: it is the DEEPEST lane on engine A's underside (its pin,
# col 5, is west of cmdA's, and both head east, so nesting forces it deepest), and
# the router kept fighting cmdA for one cell of the same corridor.
OA_PATH = [(5, 29), (5, 52), (40, 52), (40, 46), (41, 46)]
# cmdA likewise: straight west along row 34 (below every belt lane and below the
# west trunks, which stop at rows 30/31), then north up col 7 into engine A.
CMDA_PATH = [(27, 34), (7, 34), (7, 29)]
# East side: oB is SHALLOW (row 30) and cmdB DEEP (row 31), which is the nesting
# that makes them non-crossing -- and it only works with MERGE placed EAST.  With
# MERGE west, oB (pin 51) and cmdB (pin 53) are interleaved on the region boundary
# and MUST cross; that is what made every westward MERGE placement unroutable.
OB_PATH = [(51, 29), (51, 30), (54, 30), (54, 46), (53, 46)]
CMDB_PATH = [(43, 33), (44, 33), (44, 31), (53, 31), (53, 29)]


def hand_pipe(R, points):
    """Draw a fixed pipe and claim its cells as PIPE so the router routes around it."""
    import router as _r
    before = dict(R.prog.cells)
    R.prog.pipe(points)
    n = 0
    for cell, ch in R.prog.cells.items():
        if before.get(cell, ' ') != ch:
            R.grid.set(cell[0], cell[1], _r.PIPE, ch)
            n += 1
    return n


def build():
    R = Router()

    R.add_room(AX, AY, D.ENG_W, D.ENG_H)
    R.add_room(BX, BY, D.ENG_W, D.ENG_H)
    R.add_room(CX, CY, D.CTRL_W, D.CTRL_H)
    R.add_room(MX, MY, D.MERGE_W, D.MERGE_H)
    R.add_output_room(OUTX, OUTY)
    R.add_input_room(INX, INY)

    put = lambda x, y, c: R.place(x, y, c)
    D.engine(put, AX, AY)
    D.engine(put, BX, BY)
    D.control(put, CX, CY)
    D.merge_room(put, MX, MY)

    # ── border cells (the wall cell each pipe attaches to) ──────────────────
    def eng(ox, oy, col):
        return (ox + col, oy + D.ENG_H - 1)          # bottom wall

    a_ox, a_cmd = eng(AX, AY, D.X_OX), eng(AX, AY, D.X_CMD)
    b_ox, b_cmd = eng(BX, BY, D.X_OX), eng(BX, BY, D.X_CMD)

    c_a = (CX + D.CTRL_BORDER['A'][0], CY + D.CTRL_BORDER['A'][1])
    c_b = (CX + D.CTRL_BORDER['B'][0], CY + D.CTRL_BORDER['B'][1])
    c_s = (CX + D.CTRL_BORDER['S'][0], CY + D.CTRL_BORDER['S'][1])
    c_in = (CX + 2, CY + D.CTRL_H - 1)                # bottom wall, col 2

    m_s = (MX + 5, MY)                                # top wall
    m_a = (MX, MY + 4)                                # left wall
    m_b = (MX + D.MERGE_W - 1, MY + 4)                # right wall
    m_o = (MX + 5, MY + D.MERGE_H - 1)                # bottom wall

    i_out = (INX + 1, INY)                            # input room TOP wall
    o_in = (OUTX + 1, OUTY)                           # output room top wall

    # ── nets ───────────────────────────────────────────────────────────────
    n1 = hand_pipe(R, P1_PATH)
    n2 = hand_pipe(R, P2_PATH)
    hand_pipe(R, OA_PATH)
    hand_pipe(R, CMDA_PATH)
    hand_pipe(R, OB_PATH)
    hand_pipe(R, CMDB_PATH)
    print(f"# belt cells: p1={n1} p2={n2} (each must be >= 65)", file=sys.stderr)
    assert n1 >= 65 and n2 >= 65, (n1, n2)

    nets = [
        ('sel', c_s, m_s),
        ('out', m_o, o_in),
        ('inp', i_out, c_in),
    ]
    for name, src, dst in nets:
        R.add_pipe_net(src, dst, name=name)

    res = R.solve(budget=120)
    if isinstance(res, UnroutableNet):
        print("UNROUTABLE:", res, file=sys.stderr)
        return None, None
    return R, {n: (s, d) for n, s, d in nets}


if __name__ == '__main__':
    R, _ = build()
    if R is None:
        sys.exit(1)
    out = os.path.join(HERE, 'dualhead-v1.man')
    R.prog.save(out)
    print(out, R.footprint())
