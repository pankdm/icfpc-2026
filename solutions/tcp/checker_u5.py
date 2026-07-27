"""U-dispatch checker folded to 5 wide x 17 tall (checker_u6 was 6 x 15).

Width is what decides tcp's box (reader 21 + gap 2 + checker), and height had
slack, so trading one more column for two rows is a straight win.  The seq path
now turns down one column earlier: U, `-`, then `v` and the whole shift chain
runs in column x3.

    interior x1..x3, rows y1..y15

    drain path (U -> N):   s | 1 + M | > v ... < ^        back into U
    seq   path (U -> E):   - v | b ] ] ] ] d | < ^        back into U
    overflow (d, BP>0):    1 v N s H

Cells the return legs walk over (`-` at (x2,y6), `1` at (x2,y12)) only write A,
which `U` overwrites on the next receive.  `@` is a documented no-op in the
engine (lib.rs: '@' | '.' | ' ' | '`' => {}), so the init marker can sit on the
drain-return column.
"""


def emit_checker_u5(L, cx, cy, seq_j=6, drain_i=3):
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

    # ---- seq path: U -> E, folded down column x3 ----
    L.put(x(2), y(6), '-')               # A = seq - Wt = off
    L.put(x(3), y(6), 'v')
    L.put(x(3), y(7), 'b')               # BP = off
    for j in (8, 9, 10, 11):
        L.put(x(3), y(j), ']')           # BP = off >> 4
    L.put(x(3), y(12), 'd')              # off >= 16 -> CW (S->W) into the overflow gadget
    L.put(x(2), y(12), '1'); L.put(x(1), y(12), 'v')
    L.put(x(1), y(13), 'N'); L.put(x(1), y(14), 's'); L.put(x(1), y(15), 'H')
    L.put(x(3), y(13), '<')              # ok -> west, then north up x2 to the `<` at y7
    L.put(x(2), y(13), '^')

    # ---- init: BP=0 falls straight through the chain onto the return leg ----
    L.put(x(2), y(2), '@')
    L.put(x(3), y(2), 'v')

    L.room(cx, cy, 5, 17)
    return {'seqW': (cx - 1, y(seq_j)),      # flows EAST into the west wall
            'drainS': (x(drain_i), cy + 17), # flows NORTH into the south wall
            'nwall': cy, 'swall': cy + 16}
