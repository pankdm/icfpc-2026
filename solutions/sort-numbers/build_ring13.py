#!/usr/bin/env python3
"""sort-numbers 13x13 (box 169).

Two changes get the main room from 8 interior rows to 7:

  * cheaper read prologue.  `b` then `m` sets BP = n-1, so the loop runs exactly n-1 times
    and reads x2..xn itself -- the old prologue's separate `s` and second `U` disappear.
    That also makes the read path and the restart path share ONE entry (U, m, M): the read
    path drops into it from above, the restart path walks into it from the dispatch column.
  * the old row 4 held no ops at all -- it existed only to jog the man across to the descent
    column.  With the shared entry ending at (3,2) the jog fits on row 3, which the init
    cell and corridor already occupy.

Ops 41 -> 36.  Main room 10 rows -> 9 (cols 0-9, rows 0-8), which leaves a 4-row bottom band
for the 5x4 relay, and the input room slides to cols 10-12 so col 13 disappears.

Loader rules this layout is shaped by (both cost real time to rediscover):
  * an arrow whose BACKWARD neighbour is a room border is treated as a pipe start, so a
    mid-pipe cell against a wall pointing away from it becomes a phantom pipe;
  * `U`'s turn is the supplying pipe's END ARROWHEAD.

WHY THE COMPARE CYCLE IS 10 CELLS AND NOT 8 (measured, do not re-derive)
-----------------------------------------------------------------------
3 of the 10 cells are geometry: the bare turns (2,4)/(6,4) and the blank (3,4).  A grid is
bipartite, so every closed walk has EVEN length -- 9 is impossible and the only step down is
8.  An 8-cycle does exist: put `U` on a corner (it sets an ABSOLUTE direction, so it earns a
turn) and the compare run shortens to U,m,-,X, giving
    (c,4)turn (c+1,4)+ (c+2,4)s (c+3,4)d / (c+3,5)U (c+2,5)m (c+1,5)- (c,5)X
It is not reachable here, for a structural reason:

  * (6,4) is not idle -- it is the 3-WAY MERGE.  The greater path arrives heading east, the
    new-minimum branch arrives heading west, and the pass entry descends onto it heading
    south; a bare `<>^v` sets direction absolutely, so one cell serves all three, and `d`
    immediately after it tests BP once for all three.
  * In the 8-cycle `d` sits at a corner entered only FROM `s`.  Neither the new-minimum
    branch nor the pass entry can reach it, so each needs its own BP test and its own exit
    -- three exits instead of one.
  * Whichever corner holds `d`, one of the two merges breaks: `d` at NE gives a cheap exit
    but the entry cannot merge; `d` at NW lets the entry merge but its BP==0 branch leaves
    NORTH, into the rows the read prologue and entry already occupy, and routing it back
    down to the fork costs back most of the 240 ticks the shorter cycle saves.

`autotune --cases tests/stress/sort-numbers.json` converges at 1.00x on this builder, and
xray reports 0 stall and no glide corridor >= 3 cells, so the walks are already tight.

usage: python3 scratchpad/sortbox/build13.py <out.man>
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
    # read n, then BP = n-1
    (8, 1): "U", (7, 1): "b", (6, 1): "v",
    # shared entry: read a value, count it, make it the running minimum
    (6, 2): "U", (5, 2): "m", (4, 2): "M", (3, 2): "v",
    # jog across to the descent column; init cell and dispatch column
    (3, 3): ">", (6, 3): "v", (7, 3): "@", (8, 3): "^",
    (8, 2): "a", (8, 6): "q",
    # selection loop
    (2, 4): ">", (4, 4): "+", (5, 4): "s", (6, 4): "v", (7, 4): "<",
    (1, 5): "v", (2, 5): "X", (3, 5): "-", (4, 5): "U", (5, 5): "m",
    (6, 5): "d", (7, 5): "^",
    (1, 6): ">", (2, 6): ">", (3, 6): "+", (4, 6): "W", (5, 6): "s", (7, 6): "^",
    # fork, output, restart
    (1, 7): "H", (2, 7): "s", (5, 7): "W", (6, 7): "Y", (8, 7): "^",
})

# ---------------------------------------------------------------- other rooms
room(10, 0, 12, 2)              # input
put(11, 1, "I")
room(0, 10, 2, 12)              # output
put(1, 11, "O")
room(5, 9, 9, 12)               # relay, interior cols 6-8 rows 10-11
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
    os.path.dirname(os.path.abspath(__file__)), "ring13.man")
open(dest, "w").write(out)
