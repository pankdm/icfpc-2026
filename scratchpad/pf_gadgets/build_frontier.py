#!/usr/bin/env python3
"""PF GADGET 2 -- the BFS frontier FIFO ring.

Same shape as snake's body ring (scratchpad/snake_gadgets/build_fifo_ring2.py):
CTRL --FEED--> RELAY --RETURN--> CTRL, the RELAY being the two-op `r s` man that
makes an otherwise-illegal self-loop pipe legal.  The only pathfinder-specific
part is CAPACITY: the RETURN pipe is folded into a boustrophedon block so the
ring can be made arbitrarily deep without stretching the box.

  PIPE LENGTH IS CAPACITY:  capacity = feed_len + 1 (the relay man's A) + return_len

Sizing.  Measured worst case for the BFS queue on this problem (see
solutions/pathfinder/pf_model.py and the sweep in the bring-up notes):
    public cases                       19
    fully-open 14x14 interior, all
      (flag, robot) pairs              27
    400 random mazes                   27
    1500-step adversarial hill climb   30
The hard bound is 196 (two consecutive BFS levels are in opposite colour classes
of the bipartite grid, each of which holds 98 of the 196 interior cells), so a
ring of >=196 CANNOT overflow and needs no fuzzing at all.  A full ring would
deadlock the single controller man (`s` blocks forever), not crash, so the safe
default here is the provable one.

Protocol on the input pipe:
    v > 0  -> PUSH v      (no output)
    v = 0  -> POP         (emit the popped value)
A correct FIFO therefore echoes the pushed values in the SAME order.

usage: build_frontier.py [capacity] [out.man]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import littleman as lm                                          # noqa: E402

CAP = int(sys.argv[1]) if len(sys.argv) > 1 else 44   # -> true capacity 49, 1.6x the
#                                                        measured worst frontier (30)
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'frontier.man')

BAND_X0, BAND_X1 = 1, 25          # boustrophedon block for the RETURN pipe
ROW0 = 15                         # first serpentine row (below both rooms)


def build(capacity):
    p = lm.Program()

    # ---------------------------------------------------------------- input
    p.input_room(12, 1)
    p.pipe([(13, 4), (13, 5)])                    # -> CTRL top wall (13,6)

    # ----------------------------------------------------------------- CTRL
    p.room(10, 6, 10, 7)                          # interior x 11..18, y 7..11
    p.put(11, 7, '@'); p.put(12, 7, '>'); p.put(13, 7, 'r')
    p.put(14, 7, 'X'); p.put(15, 7, 'v')          # A>0 push (CW), A==0 straight
    p.put(12, 8, '^'); p.put(13, 8, 's'); p.put(14, 8, '<')     # push arm
    p.put(15, 10, '>'); p.put(16, 10, 'r'); p.put(17, 10, 'v')  # pop arm
    p.put(17, 11, '<'); p.put(16, 11, 's'); p.put(15, 11, '<')
    p.put(12, 11, '^')

    # ---------------------------------------------------------------- RELAY
    p.room(0, 6, 8, 7)                            # interior x 1..6, y 7..11
    p.put(1, 7, '@'); p.put(2, 7, '>'); p.put(3, 7, 'r'); p.put(4, 7, 'v')
    p.put(2, 8, '^'); p.put(3, 8, 's'); p.put(4, 8, '<')

    # FEED: CTRL left wall (10,8) -> RELAY right wall (7,8)
    p.pipe([(9, 8), (8, 8)])
    feed_len = 2

    # RETURN: RELAY bottom (3,12) -> serpentine block -> CTRL bottom (16,12).
    # Row 13 carries only the two vertical stubs; the horizontal runs live on
    # row 14 and below, so no pipe ever runs ALONGSIDE a room's bottom wall
    # (which would read as attached and steal that room's bindings).
    # Pick the band so the ring lands NEAR the requested capacity: an
    # oversized ring is not free -- pipe length is LATENCY as well as capacity
    # (measured: 15.5 ticks/op at cap 45 vs 58.4 at cap 253 on the same
    # shallow-queue BFS pattern), so overshooting costs ~0.24 ticks/op/cell.
    body = max(capacity - feed_len - 1 - 14, 8)
    rows = 1
    while body / rows > 40:
        rows += 2
    span = max(8, -(-body // rows))
    BAND_X1 = BAND_X0 + span - 1
    rows += 1 - (rows & 1)                        # ODD -> the last row runs EAST,
    #                                             so it ends at BAND_X1 and the
    #                                             exit leg never re-crosses it
    pts = [(3, 13), (3, 14), (BAND_X0, 14)]
    x_at, y = BAND_X0, ROW0
    for _ in range(rows):
        far = BAND_X1 if x_at == BAND_X0 else BAND_X0
        pts.append((x_at, y))
        pts.append((far, y))
        x_at, y = far, y + 1
    y -= 1
    pts.append((BAND_X1 + 1, y))                  # step out of the band, then up
    pts.append((BAND_X1 + 1, 14))
    pts.append((16, 14))
    pts.append((16, 13))
    pts = [q for i, q in enumerate(pts) if i == 0 or q != pts[i - 1]]
    p.pipe(pts, end_direction='N')

    # count the pipe cells actually drawn between the two rooms
    ret_len = _pipe_len(pts)

    # ---------------------------------------------------------------- output
    p.pipe([(20, 11), (21, 11)])
    p.output_room(22, 10)
    return p, feed_len, ret_len


def _pipe_len(pts):
    n = 0
    for i in range(len(pts) - 1):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        n += abs(x1 - x0) + abs(y1 - y0)
    return n + 1


if __name__ == '__main__':
    prog, fl, rl = build(CAP)
    prog.save(OUT)
    w, h, box = prog.footprint()
    print('wrote %s  %dx%d box=%d  feed=%d return=%d capacity=%d'
          % (OUT, w, h, box, fl, rl, fl + 1 + rl))
    print(prog.render())
