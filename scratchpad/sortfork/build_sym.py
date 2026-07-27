#!/usr/bin/env python3
"""sort-numbers 13x13, symmetric compare arms.

Change vs build_ring13.py: the compare cycle's two branches are BOTH 10 cells
(was 10 for "greater", 14 for "new minimum", 16 for "equal").  Done by giving
each arm its OWN BP test at its far end -- `d` for the north arm, `a` for the
south arm -- so neither arm has to walk around the other to reach a single
shared test cell.  Both tests are entered heading EAST and both feed the same
`<` cell that starts the westward run.

    row4  >  >  +  s  >  d  v     greater arm, its test, lap-end exit
    row5  ^  X  -  U  m  <  v     the run (heading west) + shared turn
    row6     >  +  W  s  a  v     new-minimum arm, its test, lap-end exit

Measured on ring13-v1: the new-minimum branch is taken 157 of 309 times on the
"long case" (reverse-sorted and equal data take it every time), so the 4 ticks
it wasted are ~13% of that case.
"""
import os
import sys

W, H = 13, 13
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
room(0, 0, 9, 8)
cells({
    # read n, then BP = n
    (8, 1): "U", (7, 1): "b", (6, 1): "v",
    # shared entry: read a value, make it the running minimum, count it
    (6, 2): "U", (5, 2): "M", (4, 2): "m", (3, 2): "v",
    # jog across and down into the greater arm's test
    (3, 3): ">", (5, 3): "v",
    # boot + dispatch column
    (7, 3): "@", (8, 3): "^", (8, 2): "a", (8, 6): "q",
    # greater arm (A>0): restore v, forward it, test, exit
    (2, 4): ">", (3, 4): "+", (4, 4): "s", (5, 4): ">", (6, 4): "d",
    # the run, heading west
    (1, 5): "^", (2, 5): "X", (3, 5): "-", (4, 5): "U", (5, 5): "m", (6, 5): "<",
    # equal (A==0) rejoins the greater arm
    (1, 4): ">",
    # new-minimum arm (A<0): restore v, swap, forward the old min, test, exit
    (2, 6): ">", (3, 6): "+", (4, 6): "W", (5, 6): "s", (6, 6): "a",
    # lap-end merge column
    (7, 4): "v", (7, 5): "v", (7, 6): "v", (7, 7): "Y",
    # fork: west copy emits the minimum, east copy restarts the pass
    (6, 7): "W", (3, 7): "s", (2, 7): "H", (8, 7): "^",
})

# ---------------------------------------------------------------- other rooms
room(10, 0, 12, 2)              # input
put(11, 1, "I")
room(0, 10, 2, 12)              # output
put(1, 11, "O")
room(5, 9, 9, 12)               # relay
cells({
    (6, 10): "U", (7, 10): "s", (8, 10): "v",
    (8, 11): "<", (7, 11): "@", (6, 11): "^",
})

# ---------------------------------------------------------------- pipes
pipe([(11, 3), (11, 4), (10, 4), (9, 4)])                   # input -> main
pipe([(4, 9), (4, 10), (5, 10)])                            # main -> relay
pipe([(3, 9), (3, 10), (2, 10)])                            # main -> output
pipe([(10, 11), (11, 11), (11, 12), (12, 12), (12, 11), (12, 10), (11, 10),
      (11, 9), (11, 8), (11, 7), (12, 7), (12, 6), (11, 6), (11, 5),
      (10, 5), (10, 6), (9, 6)])                            # relay -> main (16)

out = "\n".join("".join(r).rstrip() for r in g) + "\n"
dest = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "sym13.man")
open(dest, "w").write(out)
