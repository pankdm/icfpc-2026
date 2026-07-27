#!/usr/bin/env python3
"""brackets 16x16 assembler: box 289 -> 256.

Packing (verified disjoint, and every pipe routed in the leftover cells):

    M 10x11  (0,0)-(9,10)    interior 8x9  = 72 slots, 57 cells (79%)
    P  6x8   (10,0)-(15,7)   interior 4x6  = 24 slots, 21 cells  -- UNCHANGED
    O  3x3   (13,8)-(15,10)
    I  3x3   (0,11)-(2,13)
    C 13x5   (3,11)-(15,15)  interior 11x3 = 33 slots, 29 cells (88%)

C is brk4's 3-row re-lay (rows [9,1,10,9] -> [10,10,9]); its content is exactly
11 columns wide so it drops straight into an 11x3 interior.

Pipes  I -> C -> M -> P -> O, all in the 15 leftover cells:
    M->P  (10,8)'>' (11,8)'^'      into P's bottom wall
    P->O  (12,8)'v' (12,9)'>'      into O's left wall
    C->M  (10,10)'^' (10,9)'<'     into M's right wall
    I->C  (1,14)'v' (1,15)'>' (2,15)'>'  into C's bottom-left corner
Every head steps directly AWAY from its room -- an arrow that does not is
silently not a pipe and the program just deadlocks.

Binding is unambiguous everywhere: each room has at most one incoming and one
outgoing pipe, so C's seven pipe ops cannot re-bind however the rows move.

    python3 scratchpad/brk6/brk6_asm.py M8x9.txt [out.man]
"""
import os
import sys

BOX = 16
SRC = "/Users/visenbaev/icfpc26/solutions/brackets/p6v1.man"
C_ROWS = ["vs< 0aqsN}<", "@vX5M>Ubm]x", ">U^ 0 dqs}<"]
ARR = {(1, 0): ">", (-1, 0): "<", (0, 1): "v", (0, -1): "^"}

g = [[" "] * BOX for _ in range(BOX)]


def put(x, y, ch):
    if g[y][x] != " ":
        raise SystemExit("collision at (%d,%d): %r vs %r" % (x, y, g[y][x], ch))
    g[y][x] = ch


def room(x0, y0, x1, y1):
    for x in range(x0, x1 + 1):
        put(x, y0, "-" if x0 < x < x1 else "+")
        put(x, y1, "-" if x0 < x < x1 else "+")
    for y in range(y0 + 1, y1):
        put(x0, y, "|")
        put(x1, y, "|")


def pipe(cells, into):
    for i, (x, y) in enumerate(cells):
        nxt = cells[i + 1] if i + 1 < len(cells) else into
        d = (nxt[0] - x, nxt[1] - y)
        if d not in ARR:
            raise SystemExit("non-unit pipe step %s -> %s" % ((x, y), nxt))
        put(x, y, ARR[d])


def main():
    mfile = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "brk6-16.man")
    mrows = [l.rstrip("\n") for l in open(mfile).read().split("\n") if l.strip("\n") != "" or True]
    mrows = [l for l in mrows if l.strip() or True][:9]
    if len(mrows) != 9:
        raise SystemExit("M needs 9 rows, got %d" % len(mrows))
    mrows = [l.ljust(8)[:8] for l in mrows]
    n = sum(1 for l in mrows for c in l if c != " ")
    print("M interior 8x9, %d cells" % n)

    room(0, 0, 9, 10)                       # M
    room(10, 0, 15, 7)                      # P
    room(13, 8, 15, 10)                     # O
    room(0, 11, 2, 13)                      # I
    room(3, 11, 15, 15)                     # C

    for j, line in enumerate(mrows):
        for i, ch in enumerate(line):
            if ch != " ":
                put(1 + i, 1 + j, ch)

    src = [l.rstrip("\n") for l in open(SRC).read().split("\n")]
    for j in range(6):                      # P interior, straight from p6v1
        line = src[1 + j]
        for i in range(4):
            ch = line[12 + i] if 12 + i < len(line) else " "
            if ch != " ":
                put(11 + i, 1 + j, ch)

    put(14, 9, "O")
    put(1, 12, "I")

    for j, line in enumerate(C_ROWS):
        for i, ch in enumerate(line):
            if ch != " ":
                put(4 + i, 12 + j, ch)

    pipe([(10, 8), (11, 8)], (11, 7))
    pipe([(12, 8), (12, 9)], (13, 9))
    pipe([(10, 10), (10, 9)], (9, 9))
    pipe([(1, 14), (1, 15), (2, 15)], (3, 15))

    out = "\n".join("".join(r).rstrip() for r in g) + "\n"
    open(dst, "w").write(out)
    lines = out.split("\n")
    w = max(len(l) for l in lines)
    h = len([l for l in lines if l.strip()])
    print("wrote %s  %dx%d  box=%d" % (dst, w, h, max(w, h) ** 2))


if __name__ == "__main__":
    main()
