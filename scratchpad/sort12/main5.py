#!/usr/bin/env python3
"""sort-numbers main room in FIVE rows (interior 8 wide x 5 tall, room 10x7=70).

The 6-row version needed a separate row for the riser/dispatch test.  This one
folds the exit row and the dispatch together: the exit walk itself ends on the
BP test, whose "turn" goes up into the lap chain and whose "straight" runs on to
the round-entry `U`.

  c        1  2  3  4  5  6  7  8
  r1          v  M  R  m  <  b  <    lap chain, westbound; c6 = merge
  r2       >     W  q  s  a  @  U    exit walk, eastbound; c6 = BP test, c8 = round entry
  r3       ^     a  s  W  +  <       "less" arm, westbound, test at c3
  r4          a  >  m  R  -  X  v    the run, eastbound; c2 = lap test, c8 = equal lane
  r5       ^  <  d     s  +  <  <    "greater" arm, westbound, test at c3

A = value, B = running minimum, BP = values left this lap.

  boot  '@'(c7,r2) -> 'U'(c8,r2): reads n and turns NORTH (the input pipe must
        flow north into the room's SOUTH wall), then west along r1:
        b sets BP=n, '<'(c6) is the merge, m -> n-1, R reads v1, M sets B=v1,
        'v'(c2) drops down column c2.
  c2    r2 and r3 are blank -- they carry the descent southbound AND the two arm
        exits westbound, which is legal because a blank cell never turns anyone.
        (c2,r4) is the lap test: BP>0 turns CCW from south = east into the run;
        BP=0 falls through to (c2,r5)='<' and out to the exit column c1.
  run   m, R(read), '-'(A=v-min), X: CW(south)=greater arm r5, CCW(north)=less
        arm r3, straight east into the equal lane c8 which rejoins r5.
  exit  c1 carries both arm exits north to (c1,r2)='>', then east: W puts the
        minimum in A, q reads the circulating count, s sends the minimum to the
        output room, and 'a'(c6) turns north into the merge, or runs straight on
        to '@'/'U' for the next round.

Outer-layout requirements:
  * the INPUT pipe must terminate on the main room's SOUTH wall pointing north
    (that is what makes `U` face the lap chain);
  * the input terminal must sort BEFORE the return terminal in reading order;
  * 'q' must have the RETURN pipe as its nearest incoming;
  * the two arm 's' cells need the RELAY pipe as nearest outgoing, the exit 's'
    needs the OUTPUT pipe;
  * the return pipe alone must hold n-1 = 15 values.
"""

BASE = [
    " vMRm<b<",
    ">  Wqsa@",
    "^vasW+< ",
    "Wa>mR-Xv",
    "^<d s+<<",
]
BASE[1] = ">" + " " + "s" + " " + "q" + "a" + "@" + "U"

ROLE = {
    's_less': (3, 2),    # (c4,r3)
    's_gtr':  (4, 4),    # (c5,r5)
    's_exit': (2, 1),    # (c3,r2)
    'q':      (4, 1),    # (c5,r2)
}

CW = {'>': 'v', 'v': '<', '<': '^', '^': '>'}


def rotate(grid, roles, times):
    g = [list(r) for r in grid]
    rl = dict(roles)
    for _ in range(times % 4):
        h, w = len(g), len(g[0])
        ng = [[' '] * h for _ in range(w)]
        for y in range(h):
            for x in range(w):
                ng[x][h - 1 - y] = CW.get(g[y][x], g[y][x])
        g = ng
        rl = {k: (h - 1 - y, x) for k, (x, y) in rl.items()}
    return ["".join(r) for r in g], rl


if __name__ == '__main__':
    for r in BASE:
        print('[%s]' % r, len(r))
