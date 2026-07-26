#!/usr/bin/env python3
"""memory: 100-cell circulating pipe belt + rewind engine.

CONTROL (B=prev forever) sends [delta, value, op] to MEMORY.
MEMORY is stateless: rot = delta % 100, split rot = 8a + r8 with `/`,
runs an 8-relay ring `a` times and a 1-relay ring `r8` times, then taps.
Belt = 100 values circulating MEMORY -> P1 -> HOP -> P2 -> MEMORY.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools'))
from littleman import Program


# ---------------------------------------------------------------------------
# FOLD PLAN (v1 is correct but unfolded: 50x38 = box 2500, local 13.2M).
# Measured: 240 ticks/op = loop8 134 (22t per 8-relay lap) + loop1 28 + 78 walk.
# The champion addr-compare is 255 t/op, so the win must come from the 78 ticks
# of walking and from the box.  Target box <=24 (576) at ~185 t/op -> ~2.3M local.
#
# BELT PHYSICS -- CORRECTED.  My earlier "0.5 values/tick is a hard ceiling"
# was WRONG.  interp/src/lib.rs Pipe::transport iterates `occupied` in REVERSE
# (front-most value first, ascending order), so a packed run of values shifts as
# a TRAIN in a single tick -- the hole jumps to the back of the run instead of
# propagating backwards one cell per tick.  Consequences:
#   * a pipe delivers 1 value/tick at its dest and accepts 1 value/tick at its
#     source; THAT is the only ceiling.
#   * one relay man = 0.5 values/tick (`r` then `s` = 2 ticks/value).  The
#     measured "8-relay ring = 22 ticks" is this plus turn overhead -- it is a
#     property of one-man-sequential relaying, not of the belt.
#   * TWO phase-offset relay men saturate the pipe at 1 value/tick.
#   * belt pipes only need CAPACITY >= 100 (+slack), not ~2x100 for throughput,
#     so P1+P2 can drop from 235 cells to ~115 -- a large box saving.
#
# REMAINING WORK (in priority order):
#  1. Replace the one-man rings with TEST-BEFORE-FORK: the main man walks a pure
#     decision path and `Y`-forks a worker only when the test passes; the worker
#     does a fixed-size job and dies.  rot==0 is then correct BY CONSTRUCTION
#     (no lap runs at all), which also deletes the guard/bypass lanes below.
#  2. Run two workers concurrently (phase-offset by one tick) so the belt moves
#     1 cell/tick: rotation cost ~49 ticks instead of ~98+overhead.
#     CAUTION: the main man must not tap the belt before the workers finish.
#     That sync is timing-based and only safe while no worker ever blocks, which
#     needs P2 to hold ~100 values at rest (short P1, long P2, 2 pumps in HOP).
#     Fuzz hard after this change -- a desync is a silent wrong answer.
#  3. Then fold: MEM 19x18 -> ~13x16 and the whole layout toward ~24x24.
#
# SAFE TWO-PUMP SYNC (solves "main man must not tap before workers finish").
# Pipe contention is resolved by ASCENDING ENTITY ID, so the main man (oldest)
# wins every tick he wants a value.  Exploit that instead of fighting it:
#   * split the rotation in half:  M,2,W,/  ->  A = h = rot>>1, B = rot&1.
#   * `Y` fork: both copies inherit BP=h and run IDENTICAL relay rings.
#   * the main copy wins contention, so it relays 1 value / 2 ticks with no
#     stalls; the worker copy takes the alternate ticks -> 1 value/tick overall.
#   * the worker copy ends in `H`; the main copy handles the odd leftover
#     (`W` then `X` on rot&1 -> one extra relay) and then walks a few NOP cells
#     of SLACK before the tap, so it provably finishes after the worker.
# Rotation cost goes from ~2.75*rot to ~1.4*rot (ring-batched) or ~rot+slack
# (straight-chain), i.e. ~162 ticks -> ~67 ticks per op at rot=49.
# The slack cells are what make this safe -- do not remove them, and re-run the
# random-stream fuzz after any change to the ring geometry, since a desync
# shows up only as an occasional wrong value, never as a crash.
#
# KEY FOLD GADGET - vertical 2-column ring with a merged guard/exit cell.
# A bare ring always runs one lap, so rot==0 must be guarded.  Laying the ring
# vertically makes the guard bypass and the ring exit land on the SAME cell:
#     (c,0)='d'  guard   : BP>0 -> cw(east->south) into the ring at (c,1)
#                          BP==0 -> straight east to (c+1,0)
#     (c,1)='v'          : ring entry (also the turn for the returning man)
#     (c,2..h)           : "rsrsrsrs " going south
#     (c,h+1)='>' (c+1,h+1)='^'
#     (c+1,h..2)         : "rsrsrsrsm" going north
#     (c+1,1)='a'        : BP>0 -> ccw(north->west) back to (c,1)
#                          BP==0 -> straight north to (c+1,0)   <-- merges with
#     (c+1,0)='>'        : the guard bypass; one exit for both paths
# This costs 2 columns instead of 11 and removes the separate bypass lane that
# currently burns ~40 ticks of walking per op in v1.
# ---------------------------------------------------------------------------


def pipelen(pts):
    n = 1
    for i in range(len(pts) - 1):
        n += abs(pts[i + 1][0] - pts[i][0]) + abs(pts[i + 1][1] - pts[i][1])
    return n


def build():
    p = Program()
    P = p.put

    # ================= MEMORY room : cols 0-18, rows 0-17 =================
    p.room(0, 0, 19, 18)
    # -- init: A=10, BP=10, A=0, then 10 laps x 10 sends of 0 --
    for i, c in enumerate("@`10`b0v"):
        P(1 + i, 1, c)
    P(8, 2, '>')
    for i, c in enumerate("ssssss"):
        P(9 + i, 2, c)
    P(15, 2, 'v'); P(15, 3, '<')
    for i, c in enumerate("ssssm"):
        P(14 - i, 3, c)
    P(9, 3, ' '); P(8, 3, 'd')
    P(7, 3, 'v'); P(7, 4, '<'); P(1, 4, 'v')

    # -- main loop: read delta, rot = delta%100, split 8a + r8 --
    P(1, 5, '>')
    for i, c in enumerate("rM`100`W%M8W/bv"):
        P(2 + i, 5, c)
    P(16, 6, '<')
    for x in range(7, 16):
        P(x, 6, ' ')
    P(6, 6, 'a')                       # guard: BP=a>0 -> south into loop8
    P(5, 6, 'W'); P(4, 6, 'b'); P(3, 6, 'v'); P(3, 7, ' ')   # a==0 bypass

    # -- loop8 : 2x11 ring cols 6..16 rows 7-8 --
    P(6, 7, '>')
    for i, c in enumerate("rsrsrsrs "):
        P(7 + i, 7, c)
    P(16, 7, 'v'); P(16, 8, '<')
    for i, c in enumerate("rsrsrsrsm"):
        P(15 - i, 8, c)
    P(6, 8, 'd')
    P(5, 8, 'W'); P(4, 8, 'b'); P(3, 8, 'v')

    # -- loop1 guard + ring --
    P(3, 9, '>'); P(4, 9, ' '); P(5, 9, ' '); P(6, 9, 'd')
    P(6, 10, '>'); P(7, 10, 'r'); P(8, 10, 's'); P(9, 10, 'v')
    P(9, 11, '<'); P(8, 11, 'm'); P(7, 11, ' '); P(6, 11, 'd')
    P(5, 11, 'v'); P(5, 12, ' ')
    for x in range(7, 11):             # r8==0 bypass
        P(x, 9, ' ')
    P(11, 9, 'v')
    for y in range(10, 13):
        P(11, y, ' ')
    P(11, 13, '<')
    for x in range(6, 11):
        P(x, 13, ' ')

    # -- read value/op, dispatch, apply --
    P(5, 13, '<'); P(4, 13, ' '); P(3, 13, 'r'); P(2, 13, 'M'); P(1, 13, 'v')
    P(1, 14, '>'); P(2, 14, ' '); P(3, 14, 'r'); P(4, 14, 'X')
    P(5, 14, 'r'); P(6, 14, 'S')                       # read arm
    for x in range(7, 17):
        P(x, 14, ' ')
    P(17, 14, '^')
    P(4, 15, 'v'); P(4, 16, '>')                       # write arm
    P(5, 16, 'r'); P(6, 16, 'W'); P(7, 16, 's')
    for x in range(8, 17):
        P(x, 16, ' ')
    P(17, 16, '^'); P(17, 15, ' ')
    for y in range(5, 14):
        P(17, y, ' ')
    P(17, 4, '<')
    for x in range(8, 17):
        P(x, 4, ' ')
    for x in range(2, 7):
        P(x, 4, ' ')

    # ================= CONTROL room : cols 0-9, rows 28-36 =================
    CX, CY = 0, 29
    C = lambda x, y, c: P(CX + x, CY + y, c)
    p.room(CX, CY, 10, 9)
    for i, c in enumerate(">@rbr-sv"):
        C(1 + i, 1, c)
    # (1)> (2)@ (3)r=op (4)b (5)r=addr (6)- (7)s=delta (8)v
    for i, c in enumerate("+M1+M<"):
        C(8, 2 + i, c)
    # (8,2)+ (8,3)M (8,4)1 (8,5)+ (8,6)M (8,7)<
    C(7, 7, 'd')
    # write arm
    C(7, 6, 'r'); C(7, 5, 's'); C(7, 4, '<')
    C(6, 4, '1'); C(5, 4, 's'); C(4, 4, '<'); C(3, 4, '<'); C(2, 4, 'v')
    C(2, 5, ' '); C(2, 6, ' ')
    # read arm
    C(6, 7, '0'); C(5, 7, 's'); C(4, 7, '0'); C(3, 7, 's')
    C(2, 7, '<'); C(1, 7, '^')
    for y in range(2, 7):
        C(1, y, ' ')

    # ================= HOP room : cols 40-51, rows 28-31 =================
    HX, HY = 30, 32
    H = lambda x, y, c: P(HX + x, HY + y, c)
    p.room(HX, HY, 12, 4)
    H(1, 1, '>'); H(2, 1, '@')
    for i, c in enumerate("rsrsrsr"):
        H(3 + i, 1, c)
    H(10, 1, 'v')
    H(10, 2, '<')
    for i, c in enumerate("srsrsrs"):      # west from 9 -> 3
        H(9 - i, 2, c)
    H(2, 2, ' '); H(1, 2, '^')

    # ================= IO rooms =================
    p.output_room(0, 20)
    p.input_room(12, 29)

    # ================= pipes =================
    out = [(1, 18), (1, 19)]
    ipipe = [(11, 30), (10, 30)]
    cmd = [(3, 28), (3, 18)]
    p1 = [(7, 18), (7, 19), (48, 19), (48, 20), (16, 20), (16, 21), (48, 21),
          (49, 21), (49, 30), (35, 30), (35, 31)]
    p2 = [(29, 34), (17, 34), (17, 28), (47, 28), (47, 27), (5, 27), (5, 18)]
    for pts in (out, ipipe, cmd, p1, p2):
        p.pipe(pts)
    print(f"# P1={pipelen(p1)} P2={pipelen(p2)} CMD={pipelen(cmd)}", file=sys.stderr)
    return p


if __name__ == '__main__':
    prog = build()
    out = os.path.join(os.path.dirname(__file__), 'rewind-v1.man')
    prog.save(out)
    print(out, prog.footprint())
