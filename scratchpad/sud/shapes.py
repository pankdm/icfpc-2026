"""Capacity / loop-length / first-to-last-op latency for serpentine shapes.

The period of the whole pipeline is a serial chain of `segment(0, n-1)` costs, so
a room shape is only useful if it holds n ops AND walks them quickly.
"""
import sys
sys.path.insert(0, "/Users/visenbaev/icfpc26/.claude/worktrees/sud-agg/solutions/sudoku-validity")
import serp

need = [int(x) for x in sys.argv[1:]] or [16, 19, 20, 23, 24]
for n in need:
    print("=== ops = %d" % n)
    rows = []
    for H in range(3, 14, 2):
        for W in range(5, 32):
            if serp.capacity(W, H) < n:
                continue
            rows.append((serp.segment(W, H, 0, n - 1), serp.loop_len(W, H),
                         W, H, serp.capacity(W, H)))
            break
    rows.sort()
    for seg, lp, W, H, cap in rows[:6]:
        print("   walk %3d  loop %3d  room %2dx%-2d (interior %2dx%d, cap %2d)"
              % (seg, lp, W + 2, H + 2, W, H, cap))
