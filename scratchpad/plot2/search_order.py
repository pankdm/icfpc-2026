import sys, itertools
sys.path.insert(0, "scratchpad/plot2")
sys.path.insert(0, "solutions/plotter")
from router_test import route
import swar_setup as SS

NATURAL = ("addr0", "adx", "sx", "ady", "vy")   # cycle pre's body leaves
TARGET = SS.TARGET
MAPX, MAPY = SS.MAP_X, SS.MAP_Y

def rots(t):
    return [tuple(t[i:] + t[:i]) for i in range(len(t))]

def branch_cost(order_after_test, mp):
    """order_after_test: physical fifo; relabel then route to TARGET."""
    lab = tuple(mp[v] for v in order_after_test)
    r = route(lab, TARGET)
    return len(r) if r is not None else None

best = []
vals = ["adx", "ady", "sx", "vy", "addr0"]
for perm in itertools.permutations(vals[1:]):
    cyc = ("adx",) + perm
    pre_r = None
    for cand in rots(cyc):
        rr = route(NATURAL, cand)
        if rr is not None and (pre_r is None or len(rr) < pre_r):
            pre_r = len(rr)
    if pre_r is None:
        continue
    # after the test block, adx and ady move to the back -> a rotation of cyc
    i = cyc.index("adx")
    after = tuple(cyc[i:] + cyc[:i])           # adx first
    after = after[2:] + after[:2]              # adx, ady popped and re-pushed
    cx = branch_cost(after, MAPX)
    cy = branch_cost(after, MAPY)
    if cx is None or cy is None:
        continue
    best.append((max(cx, cy), pre_r + (cx + cy) / 2.0, pre_r, cx, cy, cyc))
best.sort()
for b in best[:10]:
    print("BW-1=%2d  ticks=%5.1f  pre_route=%2d  px=%2d py=%2d  %s" % b)
