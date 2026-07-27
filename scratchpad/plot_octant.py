#!/usr/bin/env python3
"""Pick the fifo order the two octant paths should converge on.

At the branch the fifo reads [vy, addr0, adx, sx, ady].  Each octant has to turn
that into the SAME sequence of labels, and the only tools are: cyclic rotations
(a fetch+push pair IS a rotation) and two registers to carry values past the
queue.  So a path is: k rotations, then five pops whose pushes come out in the
target order, with at most two values live in A/B at once.
"""
import itertools

Q0 = ["vy", "addr0", "adx", "sx", "ady"]
MAP = {
    "x": {"adx": "L", "ady": "S", "sx": "majd", "vy": "mind", "addr0": "addr0"},
    "y": {"ady": "L", "adx": "S", "vy": "majd", "sx": "mind", "addr0": "addr0"},
}


def feasible(pop, push):
    """Can `pop` (queue order) be emitted as `push` with two registers?
    Returns the op count, or None."""
    buf, i, j, ops = [], 0, 0, 0
    while j < len(push):
        if push[j] in buf:
            if buf[-1] != push[j]:
                ops += 1                       # W to bring it back into A
            buf.remove(push[j])
            ops += 1                           # s
            j += 1
        elif i < len(pop):
            if len(buf) >= 2:
                return None
            if buf:
                ops += 1                       # M/W to park the value now in A
            ops += 1                           # r
            if pop[i] == push[j]:
                ops += 1                       # s
                j += 1
            else:
                buf.append(pop[i])
            i += 1
        else:
            return None
    return ops


best = None
for perm in itertools.permutations(["L", "S", "majd", "mind", "addr0"]):
    tot, detail = 0, {}
    ok = True
    for side in ("x", "y"):
        lab = [MAP[side][v] for v in Q0]
        cheapest = None
        for k in range(len(Q0)):
            rot = Q0[k:] + Q0[:k]
            want = [v for v in rot for lb in [MAP[side][v]]]      # values, rotated
            # target as VALUES for this side
            inv = {MAP[side][v]: v for v in Q0}
            tgt = [inv[lb] for lb in perm]
            c = feasible(rot, tgt)
            if c is not None:
                c += 2 * k                                        # each rotation is r + s
                if cheapest is None or c < cheapest[0]:
                    cheapest = (c, k)
        if cheapest is None:
            ok = False
            break
        detail[side] = cheapest
        tot += cheapest[0]
    if ok and (best is None or tot < best[0]):
        best = (tot, perm, detail)

print("best common order:", best[1])
print("cost x-major:", best[2]["x"], " y-major:", best[2]["y"], " total", best[0])
for perm in itertools.permutations(["L", "S", "majd", "mind", "addr0"]):
    d = {}
    for side in ("x", "y"):
        inv = {MAP[side][v]: v for v in Q0}
        tgt = [inv[lb] for lb in perm]
        c = min([(feasible(Q0[k:] + Q0[:k], tgt) or 999) + 2 * k for k in range(5)])
        d[side] = c
    if max(d.values()) < 900 and d["x"] + d["y"] <= best[0] + 4:
        print("  ", perm, d)
