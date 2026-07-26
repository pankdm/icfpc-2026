#!/usr/bin/env python3
"""The memory dual-head CONTROL instance of the attachment enumeration.

GENERALISED into tools/bindsolve.py -- use that for new builds; this file is kept
only because it is the run that produced the numbers quoted in
solutions/memory/dualhead2_floor.py:

    3 pipes, 17 send cells  ->  68 strictly-valid assignments
    the same room with TWO sends on the selector pipe  ->  ZERO

That zero is the load-bearing result: it is why CONTROL stashes `op` in BP after
the `x` and tests it with `a` in the tail, sending `which` on reads only.  A brute
force that returns nothing is telling you the OP LAYOUT has to change, not the
geometry.
"""
W, H = 15, 27          # CONTROL outer: cols 0..14, rows 0..26; interior 1..13, 1..25

CMDA = [(5, 5), (2, 7), (5, 9), (5, 13), (2, 15), (5, 17), (5, 21), (4, 23)]
CMDB = [(8, 4), (7, 8), (9, 8), (8, 12), (7, 16), (9, 16), (10, 21), (11, 23)]
SEL = [(10, 8), (10, 16), (12, 25)]


def attach_cells():
    """Every legal outgoing-pipe attachment: the pipe cell just outside a
    non-corner wall cell.  Returns (segment_cell, wall) pairs."""
    out = []
    for y in range(1, H - 1):
        out.append(((-1, y), 'L'))
        out.append(((W, y), 'R'))
    for x in range(1, W - 1):
        out.append(((x, -1), 'T'))
        out.append(((x, H), 'B'))
    return out


def d(op, seg):
    return abs(op[0] - seg[0]) + abs(op[1] - seg[1])


def ok(a, b, s):
    for cell in CMDA:
        if not (d(cell, a) < d(cell, b) and d(cell, a) < d(cell, s)):
            return False
    for cell in CMDB:
        if not (d(cell, b) < d(cell, a) and d(cell, b) < d(cell, s)):
            return False
    for cell in SEL:
        if not (d(cell, s) < d(cell, a) and d(cell, s) < d(cell, b)):
            return False
    return True


def main():
    cands = attach_cells()
    sols = []
    for a, wa in cands:
        for b, wb in cands:
            if b == a:
                continue
            for s, ws in cands:
                if s in (a, b):
                    continue
                if ok(a, b, s):
                    sols.append((a, wa, b, wb, s, ws))
    print(len(sols), "solutions")
    for sol in sols[:40]:
        print(sol)


if __name__ == '__main__':
    main()
