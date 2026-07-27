#!/usr/bin/env python3
"""sort-numbers 14x14 fold (box 196).  Same main-room program as ring15-v1;
only the periphery changes: the ring-relay room becomes 4 wide x 6 tall
(interior 2x4) so the right strip fits in 4 columns.

usage: python3 scratchpad/sortbox/build14.py <out.man>
"""
import sys

W, H = 14, 14
g = [[" "] * W for _ in range(H)]


def put(x, y, ch):
    if not (0 <= x < W and 0 <= y < H):
        raise SystemExit(f"out of grid ({x},{y})")
    if g[y][x] != " ":
        raise SystemExit(f"collision at ({x},{y}): {g[y][x]!r} vs {ch!r}")
    g[y][x] = ch


def room(x0, y0, x1, y1):
    for x in range(x0, x1 + 1):
        put(x, y0, "-" if x0 < x < x1 else "+")
        put(x, y1, "-" if x0 < x < x1 else "+")
    for y in range(y0 + 1, y1):
        put(x0, y, "|")
        put(x1, y, "|")


def cells(spec):
    for (x, y), ch in spec.items():
        put(x, y, ch)


def pipe(path):
    for i in range(len(path) - 1):
        x, y = path[i]
        nx, ny = path[i + 1]
        d = {(1, 0): ">", (-1, 0): "<", (0, 1): "v", (0, -1): "^"}[(nx - x, ny - y)]
        put(x, y, d)


# ---------------------------------------------------------------- main room
room(0, 0, 9, 10)
cells({
    (8, 1): "U", (7, 1): "b", (6, 1): "U", (5, 1): "s", (4, 1): "v",
    (4, 2): ">", (5, 2): "m", (6, 2): "a", (7, 2): "v",
    (8, 3): "a", (8, 4): "q", (8, 5): "^",
    (7, 3): "m", (6, 3): "U", (5, 3): "M", (4, 3): "v",
    (4, 4): ">", (6, 4): "v",
    (5, 5): "@", (7, 5): ">",
    (2, 6): ">", (4, 6): "+", (5, 6): "s", (6, 6): "v", (7, 6): "<",
    (1, 7): "v", (2, 7): "X", (3, 7): "-", (4, 7): "U", (5, 7): "m",
    (6, 7): "d", (7, 7): "^",
    (1, 8): ">", (2, 8): ">", (3, 8): "+", (4, 8): "W", (5, 8): "s", (7, 8): "^",
    (1, 9): "H", (2, 9): "s", (5, 9): "W", (6, 9): "Y", (8, 9): "^",
})

# ---------------------------------------------------------------- periphery
room(11, 0, 13, 2)              # input
put(12, 1, "I")
room(1, 11, 3, 13)              # output
put(2, 12, "O")
room(10, 8, 13, 13)             # ring relay, interior cols 11-12 rows 9-12
cells({
    (11, 9): "v", (11, 10): "@", (11, 11): " ", (11, 12): "U",
    (12, 12): "^", (12, 11): "s", (12, 10): "^", (12, 9): "<",
})

pipe([(12, 3), (11, 3), (10, 3), (9, 3)])                  # input -> main
pipe([(5, 11), (5, 12), (6, 12), (7, 12), (8, 12), (9, 12), (10, 12)])  # main -> relay
pipe([(12, 7), (13, 7), (13, 6), (12, 6), (11, 6), (11, 7), (10, 7),
      (10, 6), (10, 5), (11, 5), (12, 5), (13, 5), (13, 4), (12, 4),
      (11, 4), (10, 4), (9, 4)])                           # relay -> main (16)
pipe([(0, 11), (0, 12), (1, 12)])                          # main -> output

out = "\n".join("".join(r).rstrip() for r in g) + "\n"
open(sys.argv[1], "w").write(out)
print(out, end="")
