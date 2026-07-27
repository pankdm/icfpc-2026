"""2-wide-interior checker, 4 wide x 14 tall -- one row shorter than checker_x2.

checker_x2 spent two rows turning the raw `seq` into a signed "is this in the
window" quantity:

    A = seq - (Wt+16)      `-`
    A = (Wt+16) - seq      `N`

The `N` exists only to make OK the positive branch (so `a` turns it east into
the return column). It can be paid for on the READER side instead, for free:
the reader's main loop has four blank glide cells between its `>` and its
`r b s` seq gadget, so slipping an `N` in before the `s` costs no ticks and no
box. The reader then sends **-seq** and the checker's first op becomes

    A = (-seq) + (Wt+16)   `+`      > 0 exactly when off <= 15

one cell instead of two. `+` leaves B untouched, exactly like `-` did, so the
Wt+16 invariant survives.

Interior, 12 rows x 2 columns (L = cx+1, R = cx+2):

      L  R
  r0  >  v     drain ring: U -> north -> east -> south -> back into U
  r1  1  +
  r2  s  M
  r3  U  <
  r4  +  .     seq path: A = 16 - off
  r5  b  .
  r6  a  ^     BP>0 (ok) -> CCW = east -> climbs R -> r3 '<' -> U
  r7  1  M     overflow falls straight down L | init climbs R: 4 M * M
  r8  N  *
  r9  s  M
  r10 H  4
  r11 @  ^

The three blank R cells at r4/r5 are the ok-return corridor and are also the
init man's last leg, so they must stay empty: anything there would re-run on
every accepted packet.
"""


def emit_checker_x3(L, cx, cy):
    """Room 4 wide x 14 tall at (cx,cy). Interior columns cx+1, cx+2."""
    xl, xr = cx + 1, cx + 2
    y = lambda j: cy + 1 + j

    col_l = '>1sU+ba1NsH@'
    col_r = 'v+M<  ^M*M4^'
    for j, ch in enumerate(col_l):
        if ch != ' ':
            L.put(xl, y(j), ch)
    for j, ch in enumerate(col_r):
        if ch != ' ':
            L.put(xr, y(j), ch)

    L.room(cx, cy, 4, 14)
    return {'seq_col': xl, 'drain_col': xl, 'nwall': cy, 'swall': cy + 13}
