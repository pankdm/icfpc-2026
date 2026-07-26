#!/usr/bin/env python3
"""Where is the free space in a .man, and is any of it USABLE?

A blank cell only helps if it sits in a connected region big enough to host a
structure (a ring needs ~8-12 contiguous cells with a legal walk).  Scattered
1-2 cell corridors are not exploitable.  Prints, per room, the interior fill and
the largest connected blank component, plus the free margin outside all rooms.

    python3 scratchpad/freespace.py <file.man>
"""
import sys
from collections import deque


def load(path):
    rows = open(path).read().split("\n")
    w = max(len(r) for r in rows)
    return [r.ljust(w) for r in rows], w


def find_rooms(g, w):
    """A room's top wall is a run of '-' between two '+'. Return (x0,y0,x1,y1)."""
    rooms = []
    for y, row in enumerate(g):
        x = 0
        while x < w:
            if row[x] == "+":
                x2 = x + 1
                while x2 < w and row[x2] == "-":
                    x2 += 1
                if x2 < w and row[x2] == "+" and x2 > x + 1:
                    # walk down the left wall to find the bottom
                    y2 = y + 1
                    while y2 < len(g) and x < len(g[y2]) and g[y2][x] == "|":
                        y2 += 1
                    if y2 < len(g) and g[y2][x] == "+":
                        rooms.append((x, y, x2, y2))
                x = x2
                continue
            x += 1
    return rooms


def largest_blank_component(g, x0, y0, x1, y1):
    """4-connected largest blank component strictly inside the walls."""
    cells = {(x, y)
             for y in range(y0 + 1, y1)
             for x in range(x0 + 1, x1)
             if g[y][x] == " "}
    best, seen = 0, set()
    for c in cells:
        if c in seen:
            continue
        n, q = 0, deque([c])
        seen.add(c)
        while q:
            x, y = q.popleft()
            n += 1
            for nx, ny in ((x+1, y), (x-1, y), (x, y+1), (x, y-1)):
                if (nx, ny) in cells and (nx, ny) not in seen:
                    seen.add((nx, ny))
                    q.append((nx, ny))
        best = max(best, n)
    return len(cells), best


def cycle_capacity(g, x0, y0, x1, y1):
    """Can the blank space host a RING?  A ring needs a closed walk, so the blank
    region must contain a cycle.  For each connected component: cells C, internal
    edges E -> independent cycles = E - C + 1.  Also report the largest empty
    axis-aligned rectangle, since a rectangular racetrack is the cheap shape."""
    cells = {(x, y)
             for y in range(y0 + 1, y1)
             for x in range(x0 + 1, x1)
             if g[y][x] == " "}
    seen, best_cyc, best_rect = set(), 0, (0, 0, 0)
    for c in cells:
        if c in seen:
            continue
        comp, q = set([c]), deque([c])
        seen.add(c)
        while q:
            x, y = q.popleft()
            for nx, ny in ((x+1, y), (x-1, y), (x, y+1), (x, y-1)):
                if (nx, ny) in cells and (nx, ny) not in seen:
                    seen.add((nx, ny)); comp.add((nx, ny)); q.append((nx, ny))
        edges = sum(1 for (x, y) in comp
                    for (nx, ny) in ((x+1, y), (x, y+1)) if (nx, ny) in comp)
        best_cyc = max(best_cyc, edges - len(comp) + 1)
    # largest empty rectangle over the whole interior
    for ya in range(y0 + 1, y1):
        for xa in range(x0 + 1, x1):
            if (xa, ya) not in cells:
                continue
            maxw = x1 - xa
            for yb in range(ya, y1):
                run = 0
                while xa + run < x1 and (xa + run, yb) in cells:
                    run += 1
                maxw = min(maxw, run)
                if maxw == 0:
                    break
                area = maxw * (yb - ya + 1)
                if area > best_rect[0]:
                    best_rect = (area, maxw, yb - ya + 1)
    return best_cyc, best_rect


def main():
    g, w = load(sys.argv[1])
    ne = [r for r in g if r.strip()]
    h = len(g) - sum(1 for r in g if not r.strip())
    box = max(w, h) ** 2
    occ = sum(1 for r in g for c in r if c != " ")
    print(f"grid {w}x{h}  box={box}  occupied={occ} ({100*occ/(w*h):.0f}% of grid)")

    rooms = find_rooms(g, w)
    room_area = 0
    print(f"\n{'room':>18} {'interior':>10} {'ops':>5} {'fill':>5} {"blank":>6} {"largest":>8} {"cycles":>7} {"maxrect":>7}")
    for (x0, y0, x1, y1) in sorted(rooms, key=lambda r: -(r[2]-r[0])*(r[3]-r[1])):
        iw, ih = x1 - x0 - 1, y1 - y0 - 1
        if iw <= 0 or ih <= 0:
            continue
        room_area += (x1 - x0 + 1) * (y1 - y0 + 1)
        n_ops = sum(1 for y in range(y0+1, y1) for x in range(x0+1, x1)
                    if g[y][x] != " ")
        blank, big = largest_blank_component(g, x0, y0, x1, y1)
        cyc, (ra, rw, rh) = cycle_capacity(g, x0, y0, x1, y1)
        tag = f"({x0},{y0})-({x1},{y1})"
        rect = f"{rw}x{rh}" if ra else "-"
        print(f"{tag:>18} {iw:>4}x{ih:<5} {n_ops:>5} {100*n_ops/(iw*ih):>4.0f}% "
              f"{blank:>6} {big:>8} {cyc:>7} {rect:>7}")

    # free space that belongs to no room at all
    inroom = set()
    for (x0, y0, x1, y1) in rooms:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                inroom.add((x, y))
    margin = sum(1 for y in range(h) for x in range(w)
                 if (x, y) not in inroom and g[y][x] == " ")
    print(f"\nroom bounding area {room_area} of {w*h} grid cells "
          f"({100*room_area/(w*h):.0f}%)")
    print(f"free margin outside every room: {margin} cells "
          f"({100*margin/(w*h):.0f}% of grid) — pipes live here")


main()
