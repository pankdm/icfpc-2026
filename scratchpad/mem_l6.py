#!/usr/bin/env python3
"""Rebuild memory's front end for a 6-tick pipeline cadence (was 8).

    settle = init + C * ops,  C = the Y-respawn loop length of the slowest stage.

A stage's loop length L is forced EVEN (the birth cell is adjacent to its Y) and,
for BOTH its reads and its sends on any one pipe, needs

    last_offset - first_offset < L

or the next worker overtakes this one on that pipe.  In the champion:

    parse   reads @1 @3 @7   ('<' burnt a tick before the write branch's 'r')
    pack    sends @2 @9      (*25 and -1 both after the addr send)
    fanout  reads @1 @7      sends @3 @5 @9
    block   reads @3 @6 @8   (worker born two walking cells before its 'r')

so C = 8.  This rebuild shrinks every span to <= 5:

    parse   'U' receives AND turns (to the pipe's end arrowhead) in one cell,
            so the write branch reads at @6.  Its spawner loop is the LEFT copy,
            which gets a fresh (higher) runner id each cycle and so executes
            AFTER a worker parked on the birth cell -- that worker would read a
            token and be killed by the same tick's fork, losing it -- so the
            worker gets a no-op porch to wait on.        reads 5 / sends 4
    pack    split into THREE relay rooms: split addr, then *25, then -1.  No
            room has to hold a value across a long tail. reads 5 / sends 4
    fanout  becomes r S r M S r - S                      reads 5 / sends 6
    block   its Y moves one column east so the worker is born straight onto its
            first 'r'                                    reads 5 / sends 0

The broadcast triple the blocks see, (blk, idx, 25*payload-1-idx), is unchanged,
so ladder / cells / dispatcher / output decoder are untouched.

    python3 scratchpad/mem_l6.py <src.man> <dst.man> [loop_k]     # L = 2k+2
"""
import sys

BW, NB = 19, 4


def load(path):
    rows = open(path).read().split("\n")
    w = max(len(r) for r in rows)
    return [list(r.ljust(w)) for r in rows]


def dump(g):
    return "\n".join("".join(r).rstrip() for r in g).rstrip("\n") + "\n"


def put(g, x, y, s):
    for i, ch in enumerate(s):
        g[y][x + i] = ch


def room(g, x0, x1, y0=0, y1=3):
    put(g, x0, y0, "+" + "-" * (x1 - x0 - 1) + "+")
    put(g, x0, y1, "+" + "-" * (x1 - x0 - 1) + "+")
    for y in range(y0 + 1, y1):
        g[y][x0] = "|"
        g[y][x1] = "|"


def snake(g, x0):
    """A 6-cell pipe in a 2-column gap (rooms occupy rows 0-3, gaps are free).

    Pipe capacity == pipe length.  Each front-end pipe carries 3 values per
    6-tick cycle with the producer sending at cycle offsets 2/4/7 and the
    consumer reading at 1/3/5, so a 2-cell pipe fills, the producer blocks on
    's', and the NEXT worker -- whose own 's' sits on a different cell -- gets
    to send first.  That reorders the stream.  Six slots absorb the transient.
    """
    g[2][x0] = "^"
    g[1][x0] = "^"
    g[0][x0] = ">"
    g[0][x0 + 1] = "v"
    g[1][x0 + 1] = "v"
    g[2][x0 + 1] = ">"


def relay(g, x0, x1, yx, body, init, k):
    """A 2-row relay room: worker walks west from the Y, loop returns east."""
    room(g, x0, x1)
    put(g, yx - len(body), 1, body)            # worker, west end first
    g[1][yx] = "Y"
    g[1][yx + k] = "v"
    g[2][yx + k] = "<"
    put(g, yx - len(init) + 1, 2, init)        # init man ends on '^' under Y


def build(src, dst, k=2):
    g = load(src)

    for y in range(0, 4):
        for x in range(0, 79):
            g[y][x] = " "

    put(g, 0, 1, "+-+")
    put(g, 0, 2, "|I|")
    put(g, 0, 3, "+-+")
    put(g, 3, 2, ">>")                         # I -> parse (wall at 5)

    room(g, 5, 25)                             # PARSE, interior 6..24
    put(g, 6, 2, "@9M{{NM")                    # init: B = -K
    put(g, 15 - k, 1, "v")
    put(g, 15 - k, 2, ">")
    put(g, 15, 2, "^")
    put(g, 15, 1, "Y rbrsdWsH")                # Y . r b r s d | W s H
    put(g, 21, 2, "U-sH")                      # write path: 'U' reads value @6

    snake(g, 26)
    relay(g, 28, 40, 37, "HsrsWs/r", "@5M*M^", k)   # split addr -> blk, idx
    snake(g, 41)
    relay(g, 43, 56, 52, "Hs*rsrsr", "@5M*M^", k)   # payload *= 25
    snake(g, 57)
    relay(g, 59, 72, 68, "Hs-rsrsr", "@1M^", k)     # payload -= 1

    put(g, 73, 2, ">v")                        # -> fanout (top wall row 4)
    put(g, 74, 3, "v")

    # ----------------------------- fanout (rows 5-6) ------------------------
    for x in range(58, 75):
        g[5][x] = " "
        g[6][x] = " "
    put(g, 62, 5, "HS-rSMrSrY")                # r S r M S r - S H, west end first
    put(g, 71 + k, 5, "v")
    put(g, 71 + k, 6, "<")
    put(g, 66, 6, "@5M*M^")

    for b in range(NB):                        # fanout -> block: 2 -> 6 slots
        px = 6 + b * BW
        for y in range(9, 14):
            g[y][px] = " "
        for y in range(8, 13):
            g[y][px] = "v"
        g[13][px] = "<"

    # ----------------------------- block headers ----------------------------
    if "--oldblock" in sys.argv:
        open(dst, "w").write(dump(g))
        return
    for b in range(NB):
        ox = b * BW
        for y, s in [(9, " > v"), (10, " Y <"), (11, " r W"), (12, " - %d" % b),
                     (13, "vXv "), (14, "rrr "), (15, "rbr "), (16, "HrH "),
                     (17, "v<@^"), (18, "    ")]:
            put(g, ox + 1, y, s)
        g[9][ox + 2 + k] = "v"
        g[10][ox + 2 + k] = "<"

    open(dst, "w").write(dump(g))


build(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 2)
