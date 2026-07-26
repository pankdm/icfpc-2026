#!/usr/bin/env python3
"""Calibrated tick model for `memory`, single engine vs concurrent multi-engine.

CALIBRATION (rewind-v13, the live 24x24 / avgTicks 3589 champion).  Three
synthetic probes isolate the terms, because a plain linear fit conflates them:

    100 sequential reads 0..99   (delta=0 every op)   6076 ticks
    100 reads of one address     (delta=99 every op) 24310 ticks
     50 reads of 0,2,4,..,98     (delta=1 every op)   3568 ticks

    ticks = 280 + sum_ops [ 57.5 + 10*(delta//6) + 8*(delta%6) ]

  <1% error on all three probes and on 6/7 public cases (the 7th ends on a WRITE,
  so its tail is not counted and the model over-predicts by design).

READ IT LIKE THIS: 57.5 ticks/op is the engine's fixed loop walk, and the
remainder ring's 8 ticks/relay over delta%6 adds another ~20 ticks/op of
effectively-fixed cost.  So ~77 of the dominant case's 160 ticks/op -- 48% --
does not shrink when you shorten the rotation.  That is the ceiling that decides
whether a second engine can pay for its own footprint.

================================================================================
VERDICT ON THE DUAL-BELT / DUAL-HEAD MEMORY DESIGN (third and final closure, now
on a CALIBRATED TICK MODEL rather than on routing geometry).  Reopened because
the second closure's 9.3x box argument compared a first-draft dual against a
six-iteration single engine.  That objection was correct; the design still loses,
but for a completely different and much more robust reason.

WHAT THE REOPENING GOT RIGHT -- the port geometry is NOT the blocker.
tools/bindsolve.py, run against rewind-v13's engine with its internals UNCHANGED
(12 recv cells, 13 plain send cells, the `S` excluded since it hits every
outgoing pipe), finds the planar embedding the reopening asked for:

    CMD = TOP wall (x in 1..2),  PIN = RIGHT/inner wall (y in 6..8)   4 assignments
    OX  = BOTTOM wall (x = 17),  POUT = RIGHT/inner wall (y = 10)     1 assignment

all strict, no ties.  So the "forced crossing" chain in dualhead2_floor.py is
refuted: it was an artefact of the all-four-ports-on-the-bottom-wall premise, not
of the room graph.  A BETTER arrangement also exists -- engines STACKED, belts on
the horizontal inner walls:

    CMD = LEFT,  PIN  = TOP (24 assignments) or BOTTOM (17)
    OX  = LEFT,  POUT = TOP (50)             or BOTTOM (54)

with CMD/OX on the RIGHT wall giving ZERO in every combination, i.e. both the
controller feed and the merge tap must come from the west.  Stacking is what
makes a ~30-wide box conceivable at all (two 19-wide engines side by side is 39+
wide before any channel, box >= 1521, dead on arrival).

WHY IT STILL LOSES -- the tick win is half of what everyone assumed, because
HALF OF A MEMORY OP IS NOT ROTATION.  Three synthetic probes (above) separate the
terms that a plain multi-case fit conflates:

    per op = 57.5 (engine loop walk)  +  10*(delta//6)  +  8*(delta%6)
             |________ fixed ________|     |_ 1.667/relay _|  |_ ~20 fixed _|

The remainder ring relays ONE value per 8-cell lap, so the delta%6 term averages
8*2.5 = 20 ticks and is effectively fixed too.  On the dominant public case
(delta-bar 49.86, 157 ticks/op) that is 77 fixed vs 83 rotational -- 48% of the
op does not shrink when you shorten the belt.  Every previous dual-belt estimate
priced ticks as proportional to relays and so overstated the prize.

Measured/modelled outcomes, floors from a cell census (v13 itself: 408 cells of
room area + 110 pipe cells = 518 in a 576 box, i.e. 90.0% occupancy, which is the
best density this problem has ever been folded to):

  K=2 lockstep, 2 belts of 50 in ONE room, one shared head, K men relaying
  concurrently -- no MERGE, no SEL, one CONTROL:
      avgTicks 3600 -> 2735 = 1.316x ;  floor ~731 cells -> 29x29 -> -9.8%
                                        (even at 28x28 -> -3.3%)

  K=2 concurrent, two engines on disjoint address halves, MERGE reordering:
      avgTicks 3600 -> 2103 = 1.712x ;  floor 885 cells:
          31x31 = 961  needs 92.1% occupancy (never achieved)  -> +2.6%
          32x32 = 1024 at v13's own 90.0%                      -> -3.7%
          33x33 = 1089 with realistic pipe slack               -> -9.5%
      and fw 57.5 -> 70 (a longer engine loop, which two engines plus a MERGE
      hop makes likely) already gives -5.2% at 31x31.

  K=4 anything: 1.61x-2.53x on ticks against 2.25x-3.06x on box.  Dead.

THE STRUCTURAL REASON, which is why no amount of folding rescues it: halving the
rotation costs one extra ring bank plus one extra relay station -- 230 to 350
cells on a 518-cell design -- and cells enter the score as a SQUARE box, so the
box ratio (1.46x-1.89x) outruns the tick ratio (1.32x-1.71x) in every variant.
The only branch that is positive at all needs 92% packing, and it is worth +2.6%
of a problem with <= 0.05 contest points left on it.

Floor detail for the K=2 concurrent variant (rigid rectangles, cannot overlap):
    ENGINE A / B, v13's MEM verbatim + mirrored   2 x 19x13 = 494
    relay station, 4 rings (v13's HOP is 9x7 for 2)   9x12  = 108
    CONTROL, v13's + which-bit + 2nd cmd + SEL send   10x9  =  90
    MERGE (SEL read, branch, 2 belt reads, out send)   8x6  =  48
    input + output rooms                            2 x 3x3 =  18
                                            room area total = 758
    belt feed legs, 49 standing values each (p2 >= N-1, the
      law verified at N=100 by 99 pass / 97 fail)   2 x 49  =  98
    belt return legs, cmd x2, ox x2, SEL, out, in            =  29
                                            pipe cells total = 127
                                                       TOTAL = 885
"Engines relay each other" (relay station = 0) saves only ~32 cells net: the
pass-through rings still need ~35 cells of ring area inside each engine, and
MEM's 87 interior blanks are scattered corridors, not a contiguous 7x5 block.
================================================================================
"""
import json

S_FILL, FW, DIV, LAP, REM = 280.0, 57.5, 6, 10, 8

def ops_of(t):
    i = 0; o = []
    while i < len(t):
        op = t[i]; a = t[i+1]; i += 2
        v = None
        if op == 1: v = t[i]; i += 1
        o.append((op, a, v))
    return o

def rotcost(dl, div=DIV, lap=LAP, rem=REM):
    return lap*(dl//div) + rem*(dl % div)

def single(o, B=100, fw=FW, s=S_FILL):
    prev = 0; t = s
    for op, a, v in o:
        t += fw + rotcost((a - prev) % B); prev = a + 1
    return t

def multi(o, n=2, split='odd', cmdq=3, TC=34.0, TM=12.0, fw=FW, s=S_FILL, oq=3):
    """n concurrent engines, each owning 100/n disjoint addresses on its own belt.
    CONTROL dispatches in stream order (TC ticks each) into per-engine command
    FIFOs of capacity `cmdq` ops.  Engine j runs its ops serially.  MERGE emits
    READ results in OPERATION order (head-of-line), TM ticks each; an engine may
    run at most `oq` finished reads ahead of MERGE before it blocks on `s`."""
    P = 100 // n
    prev = [0]*n; free = [s]*n; ctrl = s
    outstanding = [[] for _ in range(n)]
    reads = []               # (engine, finish) in operation order
    nread_by_eng = [0]*n
    for op, a, v in o:
        j = (a % n) if split == 'odd' else (a // P)
        p = (a // n) if split == 'odd' else (a % P)
        outstanding[j] = [x for x in outstanding[j] if x > ctrl]
        if len(outstanding[j]) >= cmdq:
            outstanding[j].sort(); ctrl = max(ctrl, outstanding[j][0])
            outstanding[j] = outstanding[j][1:]
        ctrl += TC
        dl = (p - prev[j]) % P; prev[j] = p + 1
        fin = max(free[j], ctrl) + fw + rotcost(dl)
        free[j] = fin; outstanding[j].append(fin)
        if op == 0: reads.append((j, fin))
    # MERGE, in order, with per-engine out-pipe backpressure of `oq`
    t = 0.0; emitted = [0]*n; hist = []
    for k, (j, fin) in enumerate(reads):
        # engine j could not have produced this read until MERGE had drained
        # all but oq-1 of its earlier ones
        idx = emitted[j]
        gate = hist[idx-oq] if idx >= oq else 0.0
        t = max(t, fin, gate) + TM
        emitted[j] += 1
        hist.append(t)
        if len(hist) > 4096: pass
    return t if reads else 0.0

if __name__ == '__main__':
    d = json.load(open('/Users/visenbaev/icfpc26/tests/memory.json'))
    cases = [(c['name'], ops_of([int(x) for x in c['in']])) for c in d['publicTestData']]
    base = sum(single(o) for _, o in cases)/len(cases)
    print("baseline (v13) model avgTicks %.0f   [actual 3588.9]  box 576  score %d\n"
          % (base, 576*3589))
    variants = [
      ("dual, odd/even, nominal",        dict(n=2, split='odd')),
      ("dual, low/high, nominal",        dict(n=2, split='low')),
      ("dual, cmdq=1 (no lookahead)",    dict(n=2, split='odd', cmdq=1)),
      ("dual, OPTIMISTIC cmdq=8 oq=8",   dict(n=2, split='odd', cmdq=8, oq=8)),
      ("dual, FANTASY TC=20 TM=4 q=16",  dict(n=2, split='odd', cmdq=16, oq=16, TC=20, TM=4)),
      ("dual, fw=70 (longer loop)",      dict(n=2, split='odd', fw=70)),
      ("quad, nominal",                  dict(n=4, split='odd')),
      ("quad, OPTIMISTIC",               dict(n=4, split='odd', cmdq=8, oq=8)),
    ]
    print("%-32s %8s %8s %8s   %s" % ("variant", "avgTicks", "speedup", "boxbudget", "max square"))
    for label, kw in variants:
        av = sum(multi(o, **kw) for _, o in cases)/len(cases)
        sp = base/av
        bb = 576*sp
        print("%-32s %8.0f %8.3fx %8.0f   %.1f x %.1f" % (label, av, sp, bb, bb**.5, bb**.5))
    # hard ceilings
    for label, f in [("CEILING: rotation entirely free, 1 engine",
                       lambda o: S_FILL + FW*len(o)),
                     ("CEILING: rotation free AND 2-way perfect overlap",
                       lambda o: S_FILL + FW*len(o)/2)]:
        av = sum(f(o) for _, o in cases)/len(cases)
        sp = base/av; bb = 576*sp
        print("%-32s %8.0f %8.3fx %8.0f   %.1f x %.1f" % (label[:32], av, sp, bb, bb**.5, bb**.5))
