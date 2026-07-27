"""U-dispatch checker folded to 6 wide x 15 tall (was 9 x 12).

Width is what decides tcp's box: reader 21 + gap 2 + checker.  With the polling
loop gone (see checker_u.py) nothing pins the checker's columns any more -- the
nearest-incoming-pipe rule only mattered for `r`/`q`, and `s` has a single
outgoing pipe -- so the shift chain can be folded from a row into a column.

    interior x1..x4, rows y1..y13

    drain path (U -> N):   s | 1 + M | > v ... < ^   back into U
    seq   path (U -> E):   - b | v ] ] ] ] d | < ^   back into U
    overflow (d, BP>0):    1 N v s H

Both return legs share column x2 and the (x1,y7)`^` re-entry.  Cells the return
legs walk over (`-` at (x2,y6), `N` at (x2,y11)) only ever write A, which `U`
overwrites on the next receive, so they are harmless nops for a passer-by.

Init: `@` at (x3,y2) walks east into the col-x4 shift chain with BP=0, so `d`
falls straight through and drops him onto the normal return leg into U.
"""


def emit_checker_u6(L, cx, cy, seq_j=2, drain_i=4):
    x = lambda i: cx + i
    y = lambda j: cy + j

    # ---- drain path: U -> N ----
    L.put(x(1), y(5), 's')               # emit the drained value
    L.put(x(1), y(4), '1')
    L.put(x(1), y(3), '+')               # A = 1 + Wt
    L.put(x(1), y(2), 'M')               # B = Wt+1
    L.put(x(1), y(1), '>')
    L.put(x(2), y(1), 'v')               # down x2 ...
    L.put(x(2), y(7), '<')               # ... turn west
    L.put(x(1), y(7), '^')               # shared re-entry into U

    L.put(x(1), y(6), 'U')

    # ---- seq path: U -> E, then folded down column x4 ----
    L.put(x(2), y(6), '-')               # A = seq - Wt = off
    L.put(x(3), y(6), 'b')               # BP = off
    L.put(x(4), y(6), 'v')
    for j in (7, 8, 9, 10):
        L.put(x(4), y(j), ']')           # BP = off >> 4
    L.put(x(4), y(11), 'd')              # off >= 16 -> CW (S->W) into the overflow gadget
    L.put(x(3), y(11), '1'); L.put(x(2), y(11), 'N'); L.put(x(1), y(11), 'v')
    L.put(x(1), y(12), 's'); L.put(x(1), y(13), 'H')
    L.put(x(4), y(12), '<')              # ok -> west, then north up x2 to the `<` at y7
    L.put(x(2), y(12), '^')

    # ---- init ----
    L.put(x(3), y(2), '@')
    L.put(x(4), y(2), 'v')               # BP=0 -> falls through the chain onto the return leg

    L.room(cx, cy, 6, 15)
    return {'seqW': (cx - 1, y(seq_j)),      # flows EAST into the west wall
            'drainS': (x(drain_i), cy + 15), # flows NORTH into the south wall
            'north': cy - 1}
