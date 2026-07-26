#!/usr/bin/env python3
"""Pick serpentine shapes for ROW/COL/BOX: minimise the frame, then the critical
path.  Frame is a forced vertical stack (six mask pipes must enter the gadget's
TOP wall), so:
    h = 6(dispatch) + 2 + band_h + 2 + gadget_h + 2 + 3(O)
    w = 2(gadget init-tail overhang) + band_w
"""
import sys
sys.path.insert(0, "/Users/visenbaev/icfpc26/.claude/worktrees/agent-a6899275a3d404a4a/solutions/sudoku-validity")
from serp import capacity, segment, loop_len, serp
from build_lanes2 import ROW_OPS, BOX_OPS

def shapes(n_ops):
    out = []
    for W in range(5, 20):
        for H in range(3, 16, 2):
            if capacity(W, H) >= n_ops:
                out.append((W, H))
    return out

def exits(W, H, ops):
    """columns of the two lane `s` ops -- they only need to be distinct and, since
    strips are 2 cells wide, at least 2 apart."""
    slots, _, _ = serp(W, H)
    idx = [i for i, c in enumerate(ops) if c == "s"]
    return [slots[i][0] for i in idx], idx

best = None
for rw, rh in shapes(len(ROW_OPS)):
    rx, ridx = exits(rw, rh, ROW_OPS)
    if abs(rx[0] - rx[1]) < 2: continue
    for bw, bh in shapes(len(BOX_OPS)):
        bx, bidx = exits(bw, bh, BOX_OPS)
        if abs(bx[0] - bx[1]) < 2: continue
        band_w = (rw + 2) + 1 + (rw + 2) + 1 + (bw + 2)
        band_h = max(rh + 2, bh + 2)
        w, h = 2 + band_w, 6 + 2 + band_h + 2 + 16 + 2 + 3
        box = max(w, h) ** 2
        # critical path: BOX ops before its v read (op16), and tail to the last s
        pre = segment(bw, bh, 0, 16)
        tail = segment(bw, bh, 16, bidx[1])
        rtail = segment(rw, rh, 11, ridx[1])
        key = (box, pre + tail)
        if best is None or key < best[0]:
            best = (key, dict(row=(rw, rh), box_=(bw, bh), w=w, h=h, boxscore=box,
                              pre=pre, tail=tail, rtail=rtail,
                              rloop=loop_len(rw, rh), bloop=loop_len(bw, bh),
                              rx=rx, bx=bx))
print(best[1])
print("\ncurrent ring baseline: box 2025, BOX pre_v 17, BOX tail 14, ROW tail 14")
