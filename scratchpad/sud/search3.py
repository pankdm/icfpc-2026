#!/usr/bin/env python3
"""Shape search for 3-col strips: the two lane `s` ops of a room must now be >=3
apart (strips are 3 wide), and so must consecutive exit columns across rooms.
Frame: h = 5(dispatch) + 2 + band_h + 2 + 13(gadget) + 2 + 3(O); w = 1 + band_w."""
import sys
sys.path.insert(0, "/Users/visenbaev/icfpc26/.claude/worktrees/agent-a6899275a3d404a4a/solutions/sudoku-validity")
from serp import capacity, serp, segment
from build_lanes2 import ROW_OPS, BOX_OPS

def cand(ops, sep=3):
    out = []
    for W in range(5, 22):
        for H in range(3, 16, 2):
            if capacity(W, H) < len(ops):
                continue
            slots, _, _ = serp(W, H)
            xs = [slots[i][0] for i, c in enumerate(ops) if c == "s"]
            if abs(xs[0] - xs[1]) >= sep:
                out.append((W, H, sorted(xs)))
    return out

best = []
for rw, rh, rxs in cand(ROW_OPS):
    for bw, bh, bxs in cand(BOX_OPS):
        band_w = (bw + 2) + 1 + (rw + 2) + 1 + (rw + 2)
        band_h = max(rh, bh) + 2
        h = 5 + 2 + band_h + 2 + 13 + 2 + 3
        # exit columns, BOX leftmost at band x=1
        cols = sorted([1 + 1 + x for x in bxs]
                      + [1 + (bw + 2) + 1 + 1 + x for x in rxs]
                      + [1 + (bw + 2) + 1 + (rw + 2) + 1 + 1 + x for x in rxs])
        if any(b - a < 3 for a, b in zip(cols, cols[1:])):
            continue
        # gadget spans from the init tail (@1NM, 4 cells before the first Y at
        # cols[0]-1) to one past the last strip; frame is the union with the band
        gl, gr = cols[0] - 6, cols[-1] + 2
        w = max(1 + band_w - 1, gr) - min(1, gl) + 1
        pre = segment(bw, bh, 0, 16)
        tail = segment(bw, bh, 16, [i for i, c in enumerate(BOX_OPS) if c == "s"][1])
        best.append((max(w, h) ** 2, pre + tail, (rw, rh), (bw, bh), w, h, cols))

best.sort()
for b in best[:6]:
    print(f"box={b[0]:5d} crit={b[1]:3d} ROW={b[2]} BOX={b[3]} w={b[4]} h={b[5]} cols={b[6]}")
print("\nbar to beat: box 1369 (lanes5), crit 35")
