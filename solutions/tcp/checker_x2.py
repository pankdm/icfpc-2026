"""2-wide-interior checker (4 wide x 15 tall) -- the narrow writer.

The 3-wide checker's seq path is `-` `X`, and `X`'s three-way fan needs a column
on BOTH sides of the man. With two interior columns one side is always a wall, so
`X` is out and the branch has to be `d`/`a` on BP -- which tests BP > 0 only.

Naively that puts the polarity the wrong way round: overflow turns, ok goes
straight, and then the 4-cell `1 N s H` terminal gadget and the ok-return fight
over the one remaining column. Parking **Wt+16** in B and inverting the sign with
`N` swaps them:

    A = seq - (Wt+16)      `-`
    A = (Wt+16) - seq      `N`     > 0  exactly when off <= 15  (ok)
    BP = A                 `b`
    `a`                    BP>0 -> CCW = EAST = ok ; BP<=0 -> straight = overflow

so **ok turns** off into the other column and climbs home, while **overflow goes
straight** and its gadget sits below the branch in the column it was already in.
No contention.

Cost of the inversion: B must start at Wt+16 = 16, which needs a built constant
(`4 M * M`) and therefore an init leg. Interior rows:

    3  drain above U (s 1 >, and v + M < coming back)
    1  U
    4  seq path  - N b a
    5  overflow gadget (x1) alongside the init chain (x2), + 1 row for @
    = 13 interior, 15 with walls
"""


def emit_checker_x2(L, cx, cy, seq_i=1, drain_i=1):
    """Interior x1..x2, rows y1..y13. Room 4 wide x 15 tall at (cx,cy)."""
    x = lambda i: cx + i
    y = lambda j: cy + j
    yU = 4                                   # U's row index

    # ---- drain: U -> N, ring closed across x1/x2 ----
    L.put(x(1), y(yU - 1), 's')              # emit the drained value
    L.put(x(1), y(yU - 2), '1')
    L.put(x(1), y(yU - 3), '>')
    L.put(x(2), y(yU - 3), 'v')
    L.put(x(2), y(yU - 2), '+')              # A = 1 + (Wt+16)
    L.put(x(2), y(yU - 1), 'M')              # B = Wt+17
    L.put(x(2), y(yU), '<')                  # shared re-entry into U

    L.put(x(1), y(yU), 'U')

    # ---- seq: U -> S, sign inverted so OK is the turning branch ----
    L.put(x(1), y(yU + 1), '-')
    L.put(x(1), y(yU + 2), 'N')
    L.put(x(1), y(yU + 3), 'b')
    L.put(x(1), y(yU + 4), 'a')              # BP>0 -> CCW = EAST = ok
    L.put(x(2), y(yU + 4), '^')              # ok climbs x2 back to the `<` at yU
    # overflow falls straight through in x1
    L.put(x(1), y(yU + 5), '1')
    L.put(x(1), y(yU + 6), 'N')
    L.put(x(1), y(yU + 7), 's')
    L.put(x(1), y(yU + 8), 'H')

    # ---- init: B = 16, climbing x2 into the shared '^' at yU+4 ----
    L.put(x(1), y(yU + 9), '@')
    L.put(x(2), y(yU + 9), '^')
    L.put(x(2), y(yU + 8), '4')
    L.put(x(2), y(yU + 7), 'M')              # B = 4
    L.put(x(2), y(yU + 6), '*')              # A = 16
    L.put(x(2), y(yU + 5), 'M')              # B = 16

    L.room(cx, cy, 4, 15)
    return {'seqN': (x(seq_i), cy),          # pipe must flow SOUTH into the north wall
            'drainS': (x(drain_i), cy + 15), # pipe must flow NORTH into the south wall
            'nwall': cy, 'swall': cy + 14}
