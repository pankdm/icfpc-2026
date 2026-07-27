#!/usr/bin/env python3
"""Which brackets triples actually fit 16x16?  brk3_need.py models only
width = M_w + P_w and height = max(M_h,P_h) + C_h -- it never places the two 3x3
I/O rooms, so it reports triples whose rectangles alone already exceed the box.

Hard bound: 16x16 = 256 cells, two 3x3 I/O rooms = 18, so
    M_rect + P_rect + C_rect <= 238.
The headline triple M 11x11 + P 5x11 + C 15x5 is 251 -- over by 13 before a
single cell is routed.

This enumerates rectangles that can hold each room's real cell count (M 57,
P 21, C 29), places all five rooms disjointly in 16x16 (rooms may touch but not
share a wall, so the rectangles must be disjoint cell sets), and prints the
survivors ordered by worst interior fill.

    python3 scratchpad/brk6/brk6_pack.py [max_fill]
"""
import sys

BOX = 16
M_CELLS, P_CELLS, C_CELLS = 57, 21, 29
MAXFILL = float(sys.argv[1]) if len(sys.argv) > 1 else 0.90


def rects(need):
    out = []
    for w in range(5, BOX + 1):
        for h in range(5, BOX + 1):
            iw, ih = w - 2, h - 2
            if min(iw, ih) < 3:
                continue
            if need > iw * ih * MAXFILL:
                continue
            out.append((w, h, need / (iw * ih)))
    return out


def cells(x, y, w, h):
    return {(a, b) for a in range(x, x + w) for b in range(y, y + h)}


def place_io(free):
    """Two disjoint 3x3 pockets inside `free`?  Returns them or None."""
    spots = [(x, y) for y in range(BOX - 2) for x in range(BOX - 2)
             if cells(x, y, 3, 3) <= free]
    for i, a in enumerate(spots):
        ca = cells(a[0], a[1], 3, 3)
        for b in spots[i + 1:]:
            cb = cells(b[0], b[1], 3, 3)
            if not (ca & cb):
                return a, b
    return None


def main():
    grid = cells(0, 0, BOX, BOX)
    best = []
    for mw, mh, mf in rects(M_CELLS):
        for pw, ph, pf in rects(P_CELLS):
            if mw + pw > BOX or max(mh, ph) > BOX:
                continue
            for cw, ch, cf in rects(C_CELLS):
                if mw * mh + pw * ph + cw * ch > BOX * BOX - 18:
                    continue
                top = max(mh, ph)
                if top + ch > BOX or cw > BOX:
                    continue
                used = cells(0, 0, mw, mh) | cells(mw, 0, pw, ph) | cells(0, top, cw, ch)
                if len(used) != mw * mh + pw * ph + cw * ch:
                    continue
                io = place_io(grid - used)
                if not io:
                    continue
                best.append((round(max(mf, pf, cf), 3),
                             "M %dx%d P %dx%d C %dx%d  IO %s %s"
                             % (mw, mh, pw, ph, cw, ch, io[0], io[1])))
    best.sort()
    print("feasible triples (rooms placed AND two 3x3 I/O pockets): %d" % len(best))
    for f, s in best[:12]:
        print("  worst fill %.0f%%  %s" % (100 * f, s))
    if not best:
        print("  NONE -- 16x16 is not reachable at fill <= %.0f%%" % (100 * MAXFILL))


if __name__ == "__main__":
    main()
