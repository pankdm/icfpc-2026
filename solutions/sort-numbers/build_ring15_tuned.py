#!/usr/bin/env python3
"""sort-numbers rebuild: selection sort over a pipe ring, 15x14 box (225) target.

Main room cols 0-9 rows 0-10 (interior 8x9).  Output room cols 1-3 rows 11-13.
Ring relay room cols 10-14 rows 10-13.  Input room cols 12-14 rows 0-2.

  read loop   6 cells / 6 ticks per value  (U doubles as the turn-to-west)
  sort pass   q -> a -> m U M -> d loop {m U - X (+ s | + W s)}
  fork Y      west copy: W s H (output)   east copy: up col 8 back to q

usage: python3 scratchpad/sortbox/build15.py <out.man>
"""
import os
import sys

W, H = 15, 14
g = [[" "] * W for _ in range(H)]


def put(x, y, ch):
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
    """spec: {(x,y): ch}"""
    for (x, y), ch in spec.items():
        put(x, y, ch)


def pipe(path):
    """path = [(x,y), ...]; last entry is the destination WALL cell (not drawn)."""
    for i in range(len(path) - 1):
        x, y = path[i]
        nx, ny = path[i + 1]
        d = {(1, 0): ">", (-1, 0): "<", (0, 1): "v", (0, -1): "^"}[(nx - x, ny - y)]
        put(x, y, d)


# ---------------------------------------------------------------- main room
room(0, 0, 9, 10)
MAIN = {
    # read phase (rows 1-2) + init/read-n
    (8, 1): "U", (7, 1): "b", (6, 1): "U", (5, 1): "s", (4, 1): "v",
    (4, 2): ">", (5, 2): "m", (6, 2): "a", (6, 2): "v",
    # dispatch column 8 and pass entry (row 3)
    (8, 3): "a", (8, 4): "q", (8, 5): "^",
    (7, 3): "m", (6, 3): "U", (5, 3): "M", (4, 3): "v",
    (4, 4): ">", (6, 4): "v",
    (5, 5): "@", (7, 5): ">",
    # sort loop
    (2, 6): ">", (4, 6): "+", (5, 6): "s", (6, 6): "v", (7, 6): "<",
    (1, 7): "v", (2, 7): "X", (3, 7): "-", (4, 7): "U", (5, 7): "m",
    (6, 7): "d", (7, 7): "^",
    (1, 8): ">", (2, 8): ">", (3, 8): "+", (4, 8): "W", (5, 8): "s", (7, 8): "^",
    # fork + output + restart
    (1, 9): "H", (2, 9): "s", (5, 9): "W", (6, 9): "Y", (8, 9): "^",
}
cells(MAIN)

# ---------------------------------------------------------------- other rooms
room(12, 0, 14, 2)          # input
put(13, 1, "I")
room(1, 11, 3, 13)          # output
put(2, 12, "O")
room(10, 10, 14, 13)        # ring relay
cells({
    (11, 11): "U", (12, 11): "s", (13, 11): "v",
    (11, 12): "^", (12, 12): "@", (13, 12): "<",
})

# ---------------------------------------------------------------- pipes
pipe([(11, 1), (10, 1), (9, 1)])                       # input -> main
pipe([(5, 11), (5, 12), (6, 12), (7, 12), (8, 12), (9, 12), (10, 12)])   # main -> relay
pipe([(13, 9), (13, 8), (14, 8), (14, 7), (13, 7), (12, 7), (11, 7),
      (11, 6), (12, 6), (13, 6), (14, 6), (14, 5), (13, 5), (12, 5),
      (11, 5), (10, 5), (9, 5)])                       # relay -> main (16 cells)
pipe([(0, 11), (0, 12), (1, 12)])                      # main -> output

out = "\n".join("".join(r).rstrip() for r in g) + "\n"
dest = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "ring15-auto.man")
open(dest, "w").write(out)
print(out, end="")
