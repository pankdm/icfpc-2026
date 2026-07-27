#!/usr/bin/env python3
"""Report every room's rectangle and interior fill for a .man.  Numbers only."""
import sys

p = sys.argv[1]
L = [l.rstrip("\n") for l in open(p)]
W = max(len(l.rstrip()) for l in L)
H = max(i + 1 for i, l in enumerate(L) if l.strip())
g = [(l + " " * W)[:W] for l in L[:H]]


def at(x, y):
    return g[y][x] if 0 <= x < W and 0 <= y < H else " "


rooms = []
for y in range(H):
    for x in range(W):
        if at(x, y) != "+":
            continue
        # top-left corner?
        x1 = None
        for x2 in range(x + 1, W):
            c = at(x2, y)
            if c == "+":
                x1 = x2
                break
            if c != "-":
                break
        if x1 is None:
            continue
        y1 = None
        for y2 in range(y + 1, H):
            c = at(x, y2)
            if c == "+":
                y1 = y2
                break
            if c != "|":
                break
        if y1 is None:
            continue
        if at(x1, y1) != "+":
            continue
        if any(at(xx, y1) != "-" for xx in range(x + 1, x1)):
            continue
        rooms.append((x, y, x1, y1))

rooms = [r for r in rooms if not any(
    r != s and s[0] <= r[0] and s[1] <= r[1] and r[2] <= s[2] and r[3] <= s[3]
    for s in rooms)]
print("grid %dx%d box %d   rooms %d" % (W, H, max(W, H) ** 2, len(rooms)))
tot = 0
for (x0, y0, x1, y1) in sorted(rooms, key=lambda r: (r[1], r[0])):
    iw, ih = x1 - x0 - 1, y1 - y0 - 1
    inner = [at(x, y) for y in range(y0 + 1, y1) for x in range(x0 + 1, x1)]
    blank = sum(1 for c in inner if c == " ")
    dig = sum(1 for c in inner if c.isdigit())
    area = (x1 - x0 + 1) * (y1 - y0 + 1)
    tot += area
    print("  room (%2d,%2d)-(%2d,%2d)  %2dx%-2d outer  inner %2dx%-2d = %4d"
          " blank %4d (%3.0f%%)  digits %4d  area %d"
          % (x0, y0, x1, y1, x1 - x0 + 1, y1 - y0 + 1, iw, ih, iw * ih,
             blank, 100 * blank / max(1, iw * ih), dig, area))
print("  total room area %d of %d (%.0f%%)" % (tot, W * H, 100 * tot / (W * H)))
