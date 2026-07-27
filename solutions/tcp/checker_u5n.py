"""U-dispatch checker with seq entering from the NORTH (5 wide x 18 tall).

checker_u5 took seq on the WEST wall, which forced two things:
  * the seq pipe had to reach the west wall on a straight horizontal run, so the
    reader-checker gap had to be 2 columns (a pipe needs >= 2 cells);
  * the drain had to wrap the whole checker to reach the south wall clear of the
    output room -- 12 cells of pure latency on every output-producing round.

Taking seq on the NORTH wall instead (flow SOUTH) still gives `U` two distinct
exit directions -- SOUTH for seq, NORTH for drain -- and lets the seq pipe leave
the reader eastward, cross the single gap column and turn down INTO the north
wall.  Gap 1 column, drain 3 cells.

    interior x1..x3, rows y1..y16

    drain path (U -> N):   s | 1 + M | > v ... < ^   back into U
    seq   path (U -> S):   - b ] ] ] ] a               (a: CCW from S = EAST)
    overflow (a, BP>0):    1 v N s H
    ok:                    > ^  then north up x2 to the `<` at y6

Same trap as before: `U` faces the man along the pipe's flow direction, derived
from the last two PATH cells, so the seq pipe's final segment must be SOUTH.
"""


def emit_checker_u5n(L, cx, cy, seq_i=1, drain_i=1):
    x = lambda i: cx + i
    y = lambda j: cy + j

    # ---- drain path: U -> N ----
    L.put(x(1), y(5), 's')               # emit the drained value
    L.put(x(1), y(4), '1')
    L.put(x(1), y(3), '+')               # A = 1 + Wt
    L.put(x(1), y(2), 'M')               # B = Wt+1
    L.put(x(1), y(1), '>')
    L.put(x(2), y(1), 'v')               # down x2 ...
    L.put(x(2), y(6), '<')               # ... turn west, shared re-entry into U

    L.put(x(1), y(6), 'U')

    # ---- seq path: U -> S, straight down column x1 ----
    L.put(x(1), y(7), '-')               # A = seq - Wt = off
    L.put(x(1), y(8), 'b')               # BP = off
    for j in (9, 10, 11, 12):
        L.put(x(1), y(j), ']')           # BP = off >> 4
    L.put(x(1), y(13), 'a')              # off >= 16 -> CCW (S->E) into the overflow gadget
    L.put(x(2), y(13), '1'); L.put(x(3), y(13), 'v')
    L.put(x(3), y(14), 'N'); L.put(x(3), y(15), 's'); L.put(x(3), y(16), 'H')
    L.put(x(1), y(14), '>')              # ok -> east, then north up x2 to the `<` at y6
    L.put(x(2), y(14), '^')

    # ---- init: joins the ok-return leg ----
    L.put(x(1), y(15), '@')
    L.put(x(2), y(15), '^')

    L.room(cx, cy, 5, 18)
    return {'seqN': (x(seq_i), cy),          # pipe must flow SOUTH into the north wall
            'drainS': (x(drain_i), cy + 18), # pipe must flow NORTH into the south wall
            'nwall': cy, 'swall': cy + 17}
