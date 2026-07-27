#!/usr/bin/env python3
"""sudoku-validity: lanes2 with the AND-aggregator replaced by a self-clocking
TIMER man, which is safe here only because the protocol is round-based.

The round gate releases the next cell's input ONLY after the current round's
output is emitted, so the timer cannot race ahead into a later round: its period
becomes the round period, and it only has to exceed ONE cell's processing time,
which is a constant (every round does identical work).  Requirement:

    LAP > D + 2   where D = 2 + 11 + Lpipe + 13 + 3 + 8  ticks
                  (input pipe, dispatch to the v read, dispatch->addressing pipe,
                   addressing v-read to the lane-2 send, lane pipe, strip dup path)

With Lpipe = 8 that is D = 45, so LAP must exceed 47.  TIMER_LEFT sets
LAP = 2*(43 - TIMER_LEFT); the shipped value is tuned by bisection and then
backed off, and the binding test is the public "violation on final cell" case.

Because the strips no longer emit an all-clear flag, they revert to the plain
verified mask-zero-2col grid: a strip sends ONLY on a duplicate, so on a valid
round the timer's `1` is the single output, and on an invalid round the strip's
`0` reaches the shared outgoing pipe first and the grader latches it.
"""
import os, sys
sys.path.insert(0, "/Users/visenbaev/icfpc26/tools")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from littleman import Program
from build_lanes2 import (ring, DISPATCH_OPS, ROW_OPS, COL_OPS, BOX_OPS, EXITS)

# plain mask-zero-2col: no all-clear flag, `s` fires only on a duplicate
STRIP = ["v<", "r ", "bM", "~~", "-N", "aX", "~0", ">X", " s", " H"]

YG = 22
COLS = [8, 15, 23, 30, 38, 45]        # == the six lane-exit columns
TIMER_COL = 42                        # free gap between strip 4 (38,39) and 5 (45,46)
TIMER_LEFT = 18                       # LAP = 2*(43 - TIMER_LEFT)

def strip(p, x, y):
    for j, row in enumerate(STRIP):
        for i, ch in enumerate(row):
            if ch != " ":
                p.put(x + i, y + j, ch)

def build(timer_left=TIMER_LEFT):
    p = Program()

    p.input_room(16, 0)
    p.room(22, 0, 10, 6)
    ring(p, 23, 1, 8, 4, DISPATCH_OPS)
    p.pipe([(19, 1), (21, 1)])

    p.room(5, 8, 14, 11);  rw = ring(p, 6, 9, 12, 9, ROW_OPS)
    p.room(20, 8, 14, 11); cl = ring(p, 21, 9, 12, 9, COL_OPS)
    p.room(35, 8, 16, 12); bx = ring(p, 36, 9, 14, 10, BOX_OPS)

    p.pipe([(21, 4), (17, 4), (17, 7)])
    p.pipe([(26, 6), (26, 7)])
    p.pipe([(32, 4), (36, 4), (36, 7)])

    # --- gadget room: 6 strips + the timer, 7 men from 6 Y-forks --------------
    p.room(3, YG, 45, 16)                     # interior x4..46, y23..36
    p.text(4, YG + 2, "@1NM")                 # shared init: B = -1
    chain = COLS[:-1] + [TIMER_COL]           # every fork except the last strip
    for X in chain:
        p.put(X, YG + 2, "Y")
        p.put(X, YG + 1, ">")
        p.put(X + 1, YG + 1, "v")
        p.put(X + 1, YG + 2, ">")
    p.put(COLS[-1], YG + 2, "v")              # survivor walks into strip 5
    for X in COLS:
        strip(p, X, YG + 3)                   # strips occupy y25..y34
    for X, sy in zip(COLS, (19, 19, 19, 19, 20, 20)):
        p.pipe([(X, sy), (X, YG - 1)])

    # timer: the 6th fork's south copy falls down a free column into a flat ring
    ty = YG + 13                              # y=35, first free row under the strips
    p.put(TIMER_COL, ty, "<")
    p.put(timer_left, ty, "v")
    p.put(timer_left, ty + 1, ">")
    p.put(TIMER_COL, ty + 1, "^")
    p.put(timer_left + 2, ty + 1, "1")
    p.put(timer_left + 3, ty + 1, "s")

    p.pipe([(20, YG + 16), (20, YG + 17)])    # gadget -> O
    p.output_room(19, YG + 18)
    return p, dict(row=rw, col=cl, box=bx)

def check(ck):
    ops = {"row": ROW_OPS, "col": COL_OPS, "box": BOX_OPS}
    for name, want in EXITS.items():
        idx = [i for i, c in enumerate(ops[name]) if c == "s"]
        assert tuple(ck[name][i] for i in idx) == want, name

if __name__ == "__main__":
    left = int(sys.argv[1]) if len(sys.argv) > 1 else TIMER_LEFT
    p, ck = build(left)
    check(ck)
    name = sys.argv[2] if len(sys.argv) > 2 else "lanes3.man"
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
    p.save(out)
    print(out, "footprint", p.footprint(), "LAP", 2 * (43 - left))
