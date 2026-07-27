#!/usr/bin/env python3
"""bxdecode-24x24 -> 23 wide: delete the sweeper's east wrap column, then close
the reader/checker gap.

The readout room is 19 wide (cols 0..18) against the main room's 18, and it is
the readout -- not the decode -- that sets the width. Its extra column is the
wrap column `ec`: the last slot drops onto the return row, runs east to ec,
turns north there and comes back west one cell into slot 0's entry. But slot 0's
entry is a '^' already, so the return run can simply turn north AT slot 0's
column and ec disappears.

That leaves col 18 holding only the reader<->checker pipes, so the whole
right-hand block shifts one column left and the pipes re-route with a bend
(gap 0, exactly the arrangement my own sweep16 used).
"""
import sys

SRC = '/Users/visenbaev/icfpc26/solutions/tcp/bxdecode-24x24.man'


def load(p):
    rows = open(p).read().rstrip('\n').split('\n')
    w = max(len(r) for r in rows)
    return [list(r.ljust(w)) for r in rows]


def dump(g):
    return '\n'.join(''.join(r).rstrip() for r in g) + '\n'


def find_sweeper(g):
    ys = [y for y, r in enumerate(g)
          if ''.join(r).count('sr') >= 6 or ''.join(r).count('rs') >= 6]
    R1, R2 = min(ys), max(ys)
    return R1 - 1, R1, R2, R2 + 1, R2 + 2      # R0,R1,R2,R3,Rw


def main():
    g = load(SRC)
    R0, R1, R2, R3, Rw = find_sweeper(g)
    # locate ec: the column carrying '<' on R3 and '^' on Rw
    ec = [x for x in range(len(g[0])) if g[R3][x] == '<' and g[Rw][x] == '^']
    assert len(ec) == 1, ec
    ec = ec[0]
    slot0 = ec - 1                      # slot 0's entry column ('^' on R3)
    assert g[R3][slot0] == '^', g[R3][slot0]
    g[R3][ec] = ' '
    g[Rw][ec] = ' '
    g[Rw][slot0] = '^'                  # turn north at slot 0 directly
    # pull the sweeper's east wall in one column
    east = ec + 1
    for y in range(R0 - 1, Rw + 2):
        if g[y][east] != ' ':
            g[y][ec] = g[y][east]
            g[y][east] = ' '
    # the drain pipe attached to the OLD east wall; extend it one cell west so it
    # still meets the wall in its new column
    for y in range(R0, Rw + 2):
        if g[y][east] == ' ' and g[y][east + 1] in '>-':
            g[y][east] = '>'
            if g[y][east + 1] == '>':
                g[y][east + 1] = '-'
            break
    # col 18 now carries only the reader<->checker pipes, so the checker and the
    # output room slide one column west and claim it.  The input room and its pipe
    # stay put (they sit ABOVE the checker, so they never needed the column).
    W = len(g[0])
    for y in range(6, 20):                      # checker body
        for x in range(18, W - 1):
            g[y][x] = g[y][x + 1]
        g[y][W - 1] = ' '
    for y in range(21, 24):                     # output room
        for x in range(18, W - 1):
            g[y][x] = g[y][x + 1]
        g[y][W - 1] = ' '
    g[20][19] = '^'                             # drain now enters the checker one col west
    g[20][20] = ' '
    g[20][21] = g[20][22]                       # output pipe follows the room
    g[20][22] = ' '
    open(sys.argv[1] if len(sys.argv) > 1 else '/tmp/bx_narrow.man', 'w').write(dump(g))
    print('sweeper rows', (R0, R1, R2, R3, Rw), 'ec', ec, '-> east wall', ec)


main()
