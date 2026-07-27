#!/usr/bin/env python3
"""Surgical edits to forkdecode-25x25.man (hand-written, no builder).

Two independent transforms, each applied to a COLUMN BAND so the other rooms
keep their row alignment:

drop_W   room1's `W W W W W W W W` row is redundant. Each clone loads A=digit
         with B=index; `W` turns the compare into index-digit, but `X` only
         tests the SIGN AROUND ZERO and the `H` cells sit on BOTH sides of every
         `X`, so digit-index selects the same winner and merely swaps which side
         the losers die on. Deleting the row shifts room1's lower half, the lane
         pipes and the sweeper up by one; the checker band (cols 20+) keeps its
         rows, and the drain pipe still meets the sweeper's east wall because it
         attaches at a row the shift leaves inside that wall.

flip_snake  the sweeper's serpentine ran slot 0 southbound, so the last slot
         finished heading NORTH and needed a private west column to turn down
         onto the return row. Flipping the parity makes the last slot exit
         SOUTHward straight onto the return row and that column disappears.
         (Same transform that took my own build 625 -> 576.)
"""
import sys

SRC = '/Users/visenbaev/icfpc26/solutions/tcp/forkdecode-25x25.man'


def load(path):
    rows = open(path).read().rstrip('\n').split('\n')
    w = max(len(r) for r in rows)
    return [list(r.ljust(w)) for r in rows]


def dump(g):
    return '\n'.join(''.join(r).rstrip() for r in g) + '\n'


def drop_row_in_band(g, drop_y, x0, x1):
    """Delete row `drop_y` for columns [x0,x1] only; shift that band up."""
    h = len(g)
    out = [row[:] for row in g] + [[' '] * len(g[0])]
    for y in range(drop_y, h):
        for x in range(x0, x1 + 1):
            out[y][x] = g[y + 1][x] if y + 1 < h else ' '
    while out and all(c == ' ' for c in out[-1]):
        out.pop()
    return out


def main():
    g = load(SRC)
    what = sys.argv[1] if len(sys.argv) > 1 else 'dropW'
    if what == 'dropW':
        # locate the all-W row inside room1
        ys = [y for y, r in enumerate(g)
              if ''.join(r[2:19]).replace(' ', '') == 'W' * 8]
        assert len(ys) == 1, ys
        g = drop_row_in_band(g, ys[0], 0, 19)
    if what in ('flip', 'both'):
        if what == 'both':
            ys = [y for y, r in enumerate(g)
                  if ''.join(r[2:19]).replace(' ', '') == 'W' * 8]
            assert len(ys) == 1, ys
            g = drop_row_in_band(g, ys[0], 0, 19)
        # locate the sweeper: the row of 'sr' pairs
        ys = [y for y, r in enumerate(g) if ''.join(r[2:18]) in ('srsrsrsrsrsrsrsr',
                                                                 'rsrsrsrsrsrsrsrs')]
        R1, R2 = min(ys), max(ys)
        R0, R3, Rw = R1 - 1, R2 + 1, R2 + 2
        for y in (R0, R1, R2, R3, Rw):
            for x in range(1, 19):
                g[y][x] = ' '
        for c in range(2, 18):
            north = (c % 2 == 1)         # flipped: odd columns are now northbound
            if north:                    # enter R3, r at R2, s at R1, exit R0
                g[R3][c] = '^'; g[R2][c] = 'r'; g[R1][c] = 's'; g[R0][c] = '<'
            else:                        # enter R0, r at R1, s at R2, exit R3
                g[R0][c] = 'v'; g[R1][c] = 'r'; g[R2][c] = 's'
                g[R3][c] = 'v' if c == 2 else '<'
        g[Rw][2] = '>'; g[Rw][3] = '@'; g[Rw][18] = '^'; g[R3][18] = '<'
        for y in range(R0 - 1, Rw + 2):  # west wall moves in one column
            if g[y][0] != ' ':
                g[y][1] = g[y][0]; g[y][0] = ' '

    out = sys.argv[2] if len(sys.argv) > 2 else '/tmp/fd_out.man'
    open(out, 'w').write(dump(g))
    print('wrote', out, len(g), 'rows')


main()
