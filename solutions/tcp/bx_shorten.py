#!/usr/bin/env python3
"""bxdecode 23x24 -> 23x23: the last decode level costs 3 rows, and one is free.

The bottom bit is decoded as `&` (A = seq&1), `b` (BP = A), `d` (BP>0 -> CW,
else straight).  But `&` already leaves A in {0,1}, and `X` branches on A's SIGN
-- CW if A>0, straight if A==0 -- which is the same two-way monotone split `d`
gives, without needing the value in BP at all.  A is never negative here, so
`X`'s third exit cannot fire.

    & | b | d      ->      & | X          one row saved

That row is the whole height cut: 24 -> 23 against a width already at 23, so the
box goes 576 -> 529.  The row is deleted in the READER's column band only, so
the checker keeps its row alignment; the sweeper rides up with the reader and
the drain pipe's attach row follows it.
"""
import sys

SRC = '/Users/visenbaev/icfpc26/solutions/tcp/bxdecode-23x24.man'


def load(p):
    rows = open(p).read().rstrip('\n').split('\n')
    w = max(len(r) for r in rows)
    return [list(r.ljust(w)) for r in rows]


def dump(g):
    return '\n'.join(''.join(r).rstrip() for r in g) + '\n'


def main():
    g = load(SRC)
    W = len(g[0])
    # the `b b b b b b b b` row and the `vdvd...` row directly under it
    by = [y for y, r in enumerate(g)
          if ''.join(r[1:17]).replace(' ', '') == 'b' * 8]
    assert len(by) == 1, by
    by = by[0]
    dy = by + 1
    assert 'd' in g[dy], g[dy]
    for x in range(W):                       # d -> X (branch on A, not BP)
        if g[dy][x] == 'd':
            g[dy][x] = 'X'
    band = 18                                # reader/sweeper columns only
    h = len(g)
    for y in range(by, h):
        for x in range(0, band):
            g[y][x] = g[y + 1][x] if y + 1 < h else ' '
    # the reader band rode up a row; the checker band must follow or it alone
    # holds the box at 24. Rows 0..1 of that band are empty, so slide 2..end up.
    for y in range(1, h - 1):
        for x in range(band, W):
            g[y][x] = g[y + 1][x]
    for x in range(band, W):
        g[h - 1][x] = ' '
    while g and all(c == ' ' for c in g[-1]):
        g.pop()
    open(sys.argv[1] if len(sys.argv) > 1 else '/tmp/bx_short.man', 'w').write(dump(g))
    print('dropped `b` row at', by, '; d->X at', dy)


main()
