#!/usr/bin/env python3
"""Y-fork reverser: "delay ring" design.

Both contention laws are ascending-entity-id (measured in sim/arb.js, sim/arb2.js),
so a crowd of men drains FIFO -- arbitration cannot supply the reversal. This design
buys the reversal from TIMING instead:

  * READER walks a 6-tick cycle: `>` `r` `Y` / `d` `m` `^`.
    BP is preloaded with n-1 and decremented once per lap, so the clone forked on
    lap i is born carrying A = v_i and BP = k_i = n-1-i. The same BP drives the
    reader's own loop test, so it runs exactly n laps and then falls out.

  * Each CLONE is spawned onto the SW corner of a clockwise delay RING and orbits
    it k_i times: the ring's SE corner is `d` (BP>0 -> turn, staying in the ring;
    BP<=0 -> straight, falling out southward), and `m` sits immediately after that
    corner so the first test still sees the full k_i.

    exit_i = T0 + c*i + 11 + L*(n-1-i) = const + i*(c - L)

    With ring length L > reader period c the exit times DECREASE in i: the last
    value read leaves first. Values leave (L-c) ticks apart, in reverse order,
    and walk a shared corridor to a single `s`.

Two constraints bound n:
  * capacity/collision: clones i and j share a ring cell iff c*(i-j) = 0 (mod L),
    so the design is safe only while n <= L/gcd(c, L);
  * parity: every cycle in a grid has even length, so c and L are both even and
    gcd >= 2 -- pushing n to 16 needs L >= 32, i.e. O(n^2) ticks. This build is
    therefore a mechanism demo, exact for n <= L/gcd(c,L), not a 16-general entry.

Rounds are handled for free: the reader loops back to the count-read `r` and
blocks there, and the next round's input is withheld until this round's output
has landed, so the ring is always empty when a round starts.
"""
import sys

C = 6  # reader cycle length (ticks per value)


def build(ring_w=5, ring_h=4):
    """Ring perimeter L = 2*(ring_w + ring_h) - 4."""
    W, H = 20 + ring_w, ring_h + 6
    g = [[' '] * (W + 6) for _ in range(H)]

    def put(x, y, ch):
        assert g[y][x] == ' ', f'collision at {(x, y)}: {g[y][x]!r} vs {ch!r}'
        g[y][x] = ch

    # ---- main room ------------------------------------------------------
    x0, x1 = 6, 14 + ring_w          # left/right walls (ring's east column is x1-1)
    y0, y1 = 0, H - 1                # top/bottom walls
    for x in range(x0, x1 + 1):
        g[y0][x] = g[y1][x] = '-'
    for y in range(y0, y1 + 1):
        g[y][x0] = g[y][x1] = '|'
    for x, y in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        g[y][x] = '+'

    ROW = ring_h + 1   # reader top row
    XY = 14            # column of the fork `Y`

    # ---- reader: entry, setup, 6-cell cycle -----------------------------
    put(7, ROW + 3, '@')                       # start, outside the cycle
    put(8, ROW + 3, '^')                       # ...also the round-loopback corner
    put(8, ROW + 2, '.')
    put(8, ROW + 1, '.')
    put(8, ROW, '>')
    put(9, ROW, 'r')                           # A = n
    put(10, ROW, 'b')                          # BP = n
    put(11, ROW, 'm')                          # BP = n-1
    put(12, ROW, '>')                          # cycle corner (turn east)
    put(13, ROW, 'r')                          # A = v_i
    put(XY, ROW, 'Y')                          # fork; original turns south
    put(XY, ROW + 1, 'd')                      # BP>0 -> west (loop); else south (done)
    put(13, ROW + 1, 'm')                      # BP--
    put(12, ROW + 1, '^')                      # back to the cycle corner
    put(XY, ROW + 2, '.')                      # reader falls out here...
    put(XY, ROW + 3, '<')                      # ...turns west onto the loopback row
    for x in range(9, XY):
        put(x, ROW + 3, '.')

    # ---- clone delay ring (clockwise), SW corner == the clone spawn cell -
    rx0, rx1 = XY, XY + ring_w - 1
    ry0, ry1 = ROW - ring_h, ROW - 1
    put(rx0, ry1, '^')                         # SW: spawn cell, sends clone north
    put(rx0, ry0, '>')                         # NW
    put(rx1, ry0, 'v')                         # NE
    put(rx1, ry1, 'd')                         # SE: orbit test / exit
    put(rx1 - 1, ry1, 'm')                     # BP-- , immediately AFTER the test
    for y in range(ry0 + 1, ry1):               # left + right edges
        put(rx0, y, '.')
        put(rx1, y, '.')
    for x in range(rx0 + 1, rx1):               # top + bottom edges
        put(x, ry0, '.')
        if g[ry1][x] == ' ':
            put(x, ry1, '.')

    # ---- exit corridor: ring SE -> `s` ----------------------------------
    for y in range(ROW, ROW + 2):
        put(rx1, y, '.')
    put(rx1, ROW + 2, 's')
    put(rx1, ROW + 3, 'H')

    # ---- I room + pipe (east-flowing) -----------------------------------
    for dx, ch in ((0, '+'), (1, '-'), (2, '+')):
        g[ROW - 1][1 + dx] = ch
        g[ROW + 1][1 + dx] = ch
    g[ROW][1], g[ROW][2], g[ROW][3] = '|', 'I', '|'
    g[ROW][4] = g[ROW][5] = '>'

    # ---- O room + pipe --------------------------------------------------
    ox = x1 + 3
    g[ROW + 2][x1 + 1] = g[ROW + 2][x1 + 2] = '>'
    for dx, ch in ((0, '+'), (1, '-'), (2, '+')):
        g[ROW + 1][ox + dx] = ch
        g[ROW + 3][ox + dx] = ch
    g[ROW + 2][ox], g[ROW + 2][ox + 1], g[ROW + 2][ox + 2] = '|', 'O', '|'

    return '\n'.join(''.join(r).rstrip() for r in g) + '\n'


if __name__ == '__main__':
    w = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    h = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    out = sys.argv[3] if len(sys.argv) > 3 else 'solutions/reverse-a-list/yring.man'
    txt = build(w, h)
    open(out, 'w').write(txt)
    L = 2 * (w + h) - 4
    import math
    print(txt)
    print(f'ring {w}x{h}  L={L}  c={C}  exit spacing={L - C}  safe n <= {L // math.gcd(C, L)}')
