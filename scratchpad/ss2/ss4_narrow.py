#!/usr/bin/env python3
"""subset-sum chainfield-p8: pull the two pipes that set the width in from
cols 440-448, 439x386 -> 430x386, box 192721 -> 184900 (1.042x).

Only two things occupy cols >= 440:
  pipe  7  r15->r16  len=524  -- row 0 east to (444,0), down col 444, row 29 back
  pipe 89  r87->r102 len= 87  -- row 119 east to (448,119), down col 448, row 148
The rightmost ROOM ends at col 439, and cols 432-443 rows 1-28 plus cols 434-447
rows 120-147 are completely empty, so both excursions fold into col 439/438.

Geometry only: every pipe keeps its exact cell COUNT and both endpoints, so the
program is behaviour-neutral (demonstrated today on the 95x92 grid, where an
identical-length reroute reproduced the base verdict exactly).

    python3 scratchpad/ss2/ss3_narrow.py [out.man]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "ss4-base.man")
DST = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "ss4-narrow.man")
ARR = {(1, 0): ">", (-1, 0): "<", (0, 1): "v", (0, -1): "^"}

g = [list(l.rstrip("\n")) for l in open(SRC).read().split("\n")]
while g and not "".join(g[-1]).strip():
    g.pop()
W = max(len(r) for r in g)
for r in g:
    r += [" "] * (W - len(r))


def comb(x, xt, y0, y1, teeth):
    """Go from (x,y0) down to (x,y1) inclusive, detouring into column xt for
    `teeth` two-cell bumps.  Returns the cell list."""
    ys = sorted(set(range(y0 + 1, y1 - 1, 3)))[:teeth]
    if len(ys) != teeth:
        raise SystemExit("not enough room for %d teeth" % teeth)
    t = set(ys)
    out, y = [], y0
    while y <= y1:
        out.append((x, y))
        if y in t:
            out += [(xt, y), (xt, y + 1), (x, y + 1)]
            y += 2
        else:
            y += 1
    return out


JOBS = [
    # (cells to erase, replacement cells, expected replacement length)
    ([(x, 0) for x in range(430, 435)]
     + [(434, y) for y in range(1, 30)]
     + [(x, 29) for x in range(433, 429, -1)],
     comb(429, 428, 1, 28, 5)),
    ([(x, 119) for x in range(430, 439)]
     + [(438, y) for y in range(120, 149)]
     + [(x, 148) for x in range(437, 429, -1)],
     comb(429, 428, 120, 147, 9)),
]


def main():
    for old, new in JOBS:
        if len(old) != len(new):
            raise SystemExit("length %d != %d" % (len(new), len(old)))
        for (x, y) in old:
            g[y][x] = " "
    for old, new in JOBS:
        for (x, y) in new:
            if g[y][x] != " ":
                raise SystemExit("hit %r at (%d,%d)" % (g[y][x], x, y))
    # pipe 7's replacement runs (439,0)->...->(439,29); pipe 89's (439,119)->(439,148)
    for new, tail in ((JOBS[0][1], (429, 29)), (JOBS[1][1], (429, 148))):
        for i, (x, y) in enumerate(new):
            nxt = new[i + 1] if i + 1 < len(new) else tail
            d = (nxt[0] - x, nxt[1] - y)
            if d not in ARR:
                raise SystemExit("non-unit %s->%s" % ((x, y), nxt))
            g[y][x] = ARR[d]
    # the cells that used to turn east now have to turn south / keep going
    g[0][429] = "v"
    g[29][429] = "<"
    g[119][429] = "v"
    g[148][429] = "<"
    out = "\n".join("".join(r).rstrip() for r in g) + "\n"
    open(DST, "w").write(out)
    lines = out.split("\n")
    w = max(len(l) for l in lines)
    h = len([l for l in lines if l.strip()])
    print("wrote %s  %dx%d  box=%d" % (DST, w, h, max(w, h) ** 2))


if __name__ == "__main__":
    main()
