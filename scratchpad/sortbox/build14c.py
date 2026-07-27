#!/usr/bin/env python3
"""sort-numbers 14x14 (box 196), variant C — return pipe routed through the BOTTOM band.

Relay rotated to 4 wide x 6 tall (interior 2x4) at cols 10-13 rows 8-13, freeing col 14.
The 15-cell ring-return pipe is a Hamiltonian path over cols 5-9 x rows 11-13 and lands on
main's BOTTOM wall, which puts its attach cell LATER in reading order than the input pipe's
(main's top-right corner) — the ordering the merged read loop's `U` depends on.

Main-room program is ring15-v2 with q moved (8,4) -> (8,8) to keep q binding the ring pipe.

usage: python3 scratchpad/sortbox/build14c.py <out.man>
"""
import os
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
        put(x, y, {(1, 0): ">", (-1, 0): "<", (0, 1): "v", (0, -1): "^"}[(nx - x, ny - y)])


# ---------------------------------------------------------------- main room
room(0, 0, 9, 10)
cells({
    (8, 1): "U", (7, 1): "b", (6, 1): "U", (5, 1): "s", (4, 1): "v",
    (4, 2): ">", (5, 2): "m", (6, 2): "v",
    (8, 3): "a", (7, 3): "m", (6, 3): "U", (5, 3): "M", (4, 3): "v",
    (4, 4): ">", (6, 4): "v",
    (5, 5): "@", (7, 5): ">", (8, 5): "^",
    (8, 8): "q",
    (2, 6): ">", (4, 6): "+", (5, 6): "s", (6, 6): "v", (7, 6): "<",
    (1, 7): "v", (2, 7): "X", (3, 7): "-", (4, 7): "U", (5, 7): "m",
    (6, 7): "d", (7, 7): "^",
    (1, 8): ">", (2, 8): ">", (3, 8): "+", (4, 8): "W", (5, 8): "s", (7, 8): "^",
    (1, 9): "H", (2, 9): "s", (5, 9): "W", (6, 9): "Y", (8, 9): "^",
})

# ---------------------------------------------------------------- other rooms
room(11, 2, 13, 4)              # input
put(12, 3, "I")
room(1, 11, 3, 13)              # output
put(2, 12, "O")
room(10, 8, 13, 13)             # relay, interior cols 11-12 rows 9-12
cells({
    (11, 9): "U", (11, 10): "s", (11, 11): "@", (11, 12): ">",
    (12, 12): "^", (12, 11): "^", (12, 10): "^", (12, 9): "<",
})

# ---------------------------------------------------------------- pipes
pipe([(12, 1), (12, 0), (11, 0), (10, 0), (9, 0)])          # input -> main (corner attach)
pipe([(10, 6), (11, 6), (11, 7), (11, 8)])                  # main -> relay
pipe([(9, 11), (8, 11), (8, 12), (9, 12), (9, 13), (8, 13), (7, 13), (7, 12),
      (7, 11), (6, 11), (6, 12), (6, 13), (5, 13), (5, 12), (5, 11), (5, 10)])  # relay -> main (15)
pipe([(0, 11), (0, 12), (1, 12)])                           # main -> output

out = "\n".join("".join(r).rstrip() for r in g) + "\n"
dest = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "ring14c.man")
open(dest, "w").write(out)
