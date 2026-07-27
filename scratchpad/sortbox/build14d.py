#!/usr/bin/env python3
"""sort-numbers 14x14 (box 196), variant D.

Two changes over ring15-v2:
  * the init cells on row 5 fold into row 4 ('@' beside the dispatch column), so the main
    room needs only 8 interior rows -> main is cols 0-9 rows 0-9.
  * that leaves a FOUR-row bottom band (rows 10-13), so the relay stays the proven 5 wide x
    4 tall (interior 3x2) and moves to cols 5-9 rows 10-13.  The whole right strip
    (cols 10-13 x rows 0-13) is then free for the input room and the 16-cell return pipe.

Reading order matters: the input pipe's attach (10,4) must precede the ring pipe's (10,6),
because the merged read loop's `U` takes the earlier-reading-order ready pipe.

Loader rule that shapes every pipe here: an arrow whose BACKWARD neighbour is a room border
is treated as a pipe start.  A mid-pipe cell against a wall pointing away from it therefore
becomes a phantom pipe (`pipe self-loop`, or `input room has multiple pipes`).

usage: python3 scratchpad/sortbox/build14d.py <out.man>
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
room(0, 0, 9, 9)
cells({
    # read n / merged read loop
    (8, 1): "U", (7, 1): "b", (6, 1): "U", (5, 1): "s", (4, 1): "v",
    (4, 2): ">", (5, 2): "m", (6, 2): "v",
    # dispatch column 8, pass entry on row 3, init on row 4
    (8, 3): "a", (7, 3): "m", (6, 3): "U", (5, 3): "M", (4, 3): "v",
    (4, 4): ">", (6, 4): "v", (7, 4): "@", (8, 4): "^",
    (8, 6): "q",
    # selection loop
    (2, 5): ">", (4, 5): "+", (5, 5): "s", (6, 5): "v", (7, 5): "<",
    (1, 6): "v", (2, 6): "X", (3, 6): "-", (4, 6): "U", (5, 6): "m",
    (6, 6): "d", (7, 6): "^",
    (1, 7): ">", (2, 7): ">", (3, 7): "+", (4, 7): "W", (5, 7): "s", (7, 7): "^",
    # fork, output, restart
    (1, 8): "H", (2, 8): "s", (5, 8): "W", (6, 8): "Y", (8, 8): "^",
})

# ---------------------------------------------------------------- other rooms
room(11, 0, 13, 2)              # input
put(12, 1, "I")
room(0, 11, 2, 13)              # output
put(1, 12, "O")
room(5, 10, 9, 13)              # relay, interior cols 6-8 rows 11-12
# `U`'s turn is the feeding pipe's END ARROWHEAD -- here '>' at (4,11), so the man is
# handed EAST.  (interp/ computed it from the last step inside the path instead, which is
# SOUTH for this 2-cell L; that bug is fixed, but the two rules only differ when a pipe
# turns on its final cell, so this room is exactly the case that exposes it.)
cells({
    (6, 11): "U", (7, 11): "s", (8, 11): "v",
    (8, 12): "<", (7, 12): "@", (6, 12): "^",
})

# ---------------------------------------------------------------- pipes
pipe([(12, 3), (12, 4), (11, 4), (10, 4), (9, 4)])          # input -> main
pipe([(4, 10), (4, 11), (5, 11)])                           # main -> relay
pipe([(3, 10), (3, 11), (2, 11)])                           # main -> output
pipe([(10, 11), (11, 11), (12, 11), (13, 11), (13, 10), (12, 10), (11, 10),
      (11, 9), (12, 9), (13, 9), (13, 8), (12, 8), (11, 8), (11, 7),
      (11, 6), (10, 6), (9, 6)])                            # relay -> main (16)

out = "\n".join("".join(r).rstrip() for r in g) + "\n"
dest = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "ring14d.man")
open(dest, "w").write(out)
