#!/usr/bin/env python3
"""Room bounding boxes + occupancy of a .man, sorted by area.

Answers "which room sets the footprint dimension" without pasting the grid.

    python3 s4/scratchpad/floormap.py <file.man>
"""
import sys


def load(path):
    rows = open(path).read().split("\n")
    w = max(len(r) for r in rows)
    return [r.ljust(w) for r in rows], w


def find_rooms(g, w):
    rooms = []
    for y, row in enumerate(g):
        x = 0
        while x < w:
            if row[x] == "+":
                x2 = x + 1
                while x2 < w and row[x2] == "-":
                    x2 += 1
                if x2 < w and row[x2] == "+" and x2 > x + 1:
                    y2 = y + 1
                    while y2 < len(g) and g[y2][x] == "|":
                        y2 += 1
                    if y2 < len(g) and g[y2][x] == "+":
                        rooms.append((x, y, x2, y2))
                x = x2
                continue
            x += 1
    return rooms


def main(path):
    g, w = load(path)
    h = len(g)
    rooms = find_rooms(g, w)
    # global footprint
    ys = [y for y, r in enumerate(g) if r.strip()]
    xs = [x for y in ys for x in range(w) if g[y][x] != " "]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    fw, fh = x1 - x0 + 1, y1 - y0 + 1
    print(f"footprint {fw}x{fh} box {max(fw, fh)**2:,}  origin ({x0},{y0})")
    rooms.sort(key=lambda r: -((r[2] - r[0]) * (r[3] - r[1])))
    print(f"{len(rooms)} rooms")
    for (rx0, ry0, rx1, ry1) in rooms[:20]:
        rw, rh = rx1 - rx0 + 1, ry1 - ry0 + 1
        glyphs = sum(1 for y in range(ry0 + 1, ry1)
                     for x in range(rx0 + 1, rx1) if g[y][x] != " ")
        area = (rw - 2) * (rh - 2)
        print(f"  x[{rx0:4d}..{rx1:4d}] y[{ry0:4d}..{ry1:4d}] {rw:4d}x{rh:4d} "
              f"glyphs {glyphs:5d} dens {100.0*glyphs/max(area,1):5.1f}%")
    # row/column occupancy outside the biggest room
    big = rooms[0]
    print("\nrows below/above the big room that are non-blank:")
    for y in range(y0, y1 + 1):
        if y > big[3] or y < big[1]:
            n = sum(1 for x in range(w) if g[y][x] != " ")
            if n:
                pass
    above = [y for y in range(y0, big[1]) if g[y].strip()]
    below = [y for y in range(big[3] + 1, y1 + 1) if g[y].strip()]
    print(f"  above: {len(above)} rows ({min(above) if above else '-'}..{max(above) if above else '-'})")
    print(f"  below: {len(below)} rows ({min(below) if below else '-'}..{max(below) if below else '-'})")
    leftof = [x for x in range(x0, big[0]) if any(g[y][x] != " " for y in range(h))]
    rightof = [x for x in range(big[2] + 1, x1 + 1) if any(g[y][x] != " " for y in range(h))]
    print(f"  left of big room: {len(leftof)} cols; right of big room: {len(rightof)} cols")


if __name__ == "__main__":
    main(sys.argv[1])
