#!/usr/bin/env python3
"""sort-numbers 12x12: the main-room op grid (interior 8 wide x 6 tall).

Columns c1..c8 left->right, rows r1..r6 top->bottom:

  r1  v M R m < b R <   round entry (from c8) merges the lap chain at c5 ('<')
  r2          ^   @ a   c8 = dispatch test; c5 = riser; c7 = boot man
  r3  v a s W + <       "less" arm, westbound, with its BP test at c2
  r4  a > m R - X v     the run, eastbound: m, R(read), -(A-=B), X(3-way branch)
  r5  v d   s + < <     "greater" arm, westbound, with its BP test at c2
  r6  > W       s q ^   exit: W(A=min), s(->output), q(BP=count), back up c8

A = value, B = running minimum, BP = values left this lap.

Flow.  Boot '@'(c7,r2) -> 'a'(c8,r2) with BP=0 -> north -> '<'(c8,r1) -> west:
R reads n, b sets BP=n, '<' is the merge cell, m -> n-1, R reads v1, M sets
B=v1, 'v' drops to the c1 column.  c1: r2 blank, r3 'v', r4 'a' = the lap test
(BP>0 turns CCW from south = east into the run; BP=0 falls through r5 'v' to the
exit row).  The run: m decrements, R reads the next value, '-' gives A=v-min,
X branches -- CW(south) to the greater arm, CCW(north) to the less arm, straight
east into the equal lane (c7 'v' then c7/c6 '<' joins the greater arm).  Each arm
restores A with '+', sends the loser with 's', and ends on its own BP test at c2
which either re-enters the run at (c2,r4) or falls west to c1 and exits.

Exit row: W puts the minimum in A, s sends it to the output room, q sets BP to
the number of values still circulating, then c8 '^' returns to the dispatch.

Outer-layout requirements (checked by search.py):
  * the input pipe's terminal sorts BEFORE the return pipe's in reading order
    (main's 'R' takes the first ready pipe in reading order and lap 1 must drain
    input; a recirculated value read during lap 1 breaks the invariant);
  * 'q' must have the RETURN pipe as its nearest incoming;
  * the two arm 's' cells must have the RELAY pipe as nearest outgoing and the
    exit 's' must have the OUTPUT pipe as nearest outgoing;
  * the return pipe alone must hold n-1 = 15 values, because main reads lap 1
    from the input pipe and never drains the return pipe until the lap is over.
"""

BASE = [
    "vMRm<bR<",
    "    ^  a",
    "vasW+<@^",
    "a>mR-Xv ",
    "vd s+<< ",
    ">W   sq^",
]

# (col,row), 0-based inside the interior
ROLE = {
    's_less':  (2, 2),
    's_gtr':   (3, 4),
    's_exit':  (5, 5),
    'q':       (6, 5),
}

CW = {'>': 'v', 'v': '<', '<': '^', '^': '>'}


def rotate(grid, roles, times):
    """rotate the interior grid clockwise `times` * 90 degrees, remapping arrows.
    'X'/'d'/'a' keep their CW/CCW meaning under rotation (not under reflection)."""
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


# relay interior is 3x2 (or 2x3 rotated); one corner must be 'U' and its turn
# direction is the incoming pipe's flow direction.
def relay_cells(w, h, flow):
    """Return {(x,y): ch} for a relay interior of size w x h (6 cells, a single
    cycle) given the incoming pipe's flow direction `flow`.  None if impossible."""
    if (w, h) == (3, 2):
        cyc = [(0, 0), (1, 0), (2, 0), (2, 1), (1, 1), (0, 1)]
    elif (w, h) == (2, 3):
        cyc = [(0, 0), (1, 0), (1, 1), (1, 2), (0, 2), (0, 1)]
    else:
        return []
    out = []
    for rev in (False, True):
        c = list(reversed(cyc)) if rev else cyc
        n = len(c)
        dirs = [(c[(i + 1) % n][0] - c[i][0], c[(i + 1) % n][1] - c[i][1]) for i in range(n)]
        for i in range(n):
            if dirs[i] != flow:
                continue
            if dirs[i - 1] == dirs[i]:
                continue                      # 'U' must be a turn cell
            # 's' on the first straight cell after i, '@' on the other straight
            straight = [j for j in range(n) if dirs[j - 1] == dirs[j]]
            if len(straight) != 2:
                continue
            order = [(i + k) % n for k in range(1, n)]
            sj = next(j for j in order if j in straight)
            aj = next(j for j in straight if j != sj)
            cells = {}
            ok = True
            for j in range(n):
                if j == i:
                    cells[c[j]] = 'U'
                elif j == sj:
                    cells[c[j]] = 's'
                elif j == aj:
                    cells[c[j]] = '@'
                elif dirs[j - 1] != dirs[j]:
                    cells[c[j]] = {(1, 0): '>', (-1, 0): '<', (0, 1): 'v', (0, -1): '^'}[dirs[j]]
                else:
                    ok = False
                    break
            if ok:
                out.append(cells)
    return out
