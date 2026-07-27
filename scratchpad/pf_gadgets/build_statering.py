#!/usr/bin/env python3
"""PF GADGET 3 -- the canonical-order state ring (snake's rotating register file).

A ring holding K scalars that are popped and pushed back in ONE FIXED ORDER, so
every access is O(1) amortised instead of LLLM's O(ring) random access.  For
pathfinder the canonical order is one lap per BFS pop, e.g.

    [ cur, robot, flag, tag, level, phase, ... ]

The rig is the frontier rig with one character changed: the pop arm's `s`
becomes `S`.  `S` sends A to EVERY outgoing pipe atomically, and the controller's
outgoing pipes are exactly (ring FEED, output) -- so one op both PUSHES THE VALUE
BACK and reports it.  That is the whole "rotating register file": pop, use,
push back, and the ring is intact whatever the branch does (finding 7).

Protocol on the input pipe:
    v != 0  -> PRELOAD v into the ring (in canonical order)
    v == 0  -> LAP: pop the next scalar, echo it, and push it back
So feeding [s0..s(K-1)] then 3K zeros must echo the canonical order three times.

usage: build_statering.py [K] [out.man]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import littleman as lm                                          # noqa: E402

K = int(sys.argv[1]) if len(sys.argv) > 1 else 8
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'statering.man')


def build(k):
    p = lm.Program()

    p.input_room(12, 1)
    p.pipe([(13, 4), (13, 5)])                    # -> CTRL top wall (13,6)

    # ----------------------------------------------------------------- CTRL
    p.room(10, 6, 10, 7)                          # interior x 11..18, y 7..11
    p.put(11, 7, '@'); p.put(12, 7, '>'); p.put(13, 7, 'r')
    p.put(14, 7, 'X'); p.put(15, 7, 'v')          # A!=0 preload (CW), 0 -> lap
    p.put(12, 8, '^'); p.put(13, 8, 's'); p.put(14, 8, '<')     # preload push
    p.put(15, 10, '>'); p.put(16, 10, 'r'); p.put(17, 10, 'v')  # LAP: pop
    p.put(17, 11, '<'); p.put(16, 11, 'S'); p.put(15, 11, '<')  # echo + push back
    p.put(12, 11, '^')

    # ---------------------------------------------------------------- RELAY
    p.room(0, 6, 8, 7)
    p.put(1, 7, '@'); p.put(2, 7, '>'); p.put(3, 7, 'r'); p.put(4, 7, 'v')
    p.put(2, 8, '^'); p.put(3, 8, 's'); p.put(4, 8, '<')

    p.pipe([(9, 8), (8, 8)])                      # FEED, len 2
    # RETURN sized so capacity = 2 + 1 + return_len is just above k
    span = max(4, k - 4)
    p.pipe([(3, 13), (3, 14), (3 + span, 14), (3 + span, 13),
            (16, 13)], end_direction='N')
    ret = 2 + span + 1 + max(0, 16 - (3 + span))
    p.pipe([(20, 11), (21, 11)])
    p.output_room(22, 10)
    return p, 2, ret


if __name__ == '__main__':
    prog, fl, rl = build(K)
    prog.save(OUT)
    w, h, box = prog.footprint()
    print('wrote %s  %dx%d box=%d  K=%d capacity~%d' % (OUT, w, h, box, K, fl + 1 + rl))
    print(prog.render())
