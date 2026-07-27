"""tcp: compact checker — an 8-cell poll ring instead of the 45-tick spin loop.

sweep8's checker (emit_checker_folded3, 9x19) spends its life on two long walks:
  * re-poll spin  ~45 ticks  (16-cell riser up col x1 + 8-cell riser down x7)
  * per drained value ~21 ticks (gadget west, then a 4+6 cell loopback rail)
Both are pure glide.  This one keeps the same algorithm but folds it into a
6x9 interior:

  ring (cols 1-4, rows 4-5), 8 ticks/lap:
      > q[SEQ] a v      a: BP>0 -> CCW(E->N) into the seq body
      ^ a q[DRAIN] <    a: BP>0 -> CCW(W->S) into the drain body

  seq body (5 ticks back to the ring):
      r  A=seq          B is held at W+16 all the time, so
      -  A=off-16       X splits three ways: A<0 (off<=15) -> CCW = normal,
      X                 A==0/A>0 (off>=16) -> straight/CW, both -> `1 N s`.

  drain body (10-tick loop while values keep coming):
      r s > 1 ^ + M     then the ring corner `<` feeds q[DRAIN] again.

Pipe targeting is by Manhattan distance: SEQ attaches west at local row 2,
DRAIN east at local row 6, which makes every q/r in the block lock onto the
pipe it wants (checked in the module docstring table of _NEAREST below).
"""


# (cell, wants) for every q/r, with the distances that make it unambiguous:
#   (2,4) q  SEQ  : seq 3+2=5   drain 6+2=8
#   (3,5) q  DRAIN: seq 4+3=7   drain 1+5=6
#   (3,3) r  SEQ  : seq 4+1=5   drain 1+7=8
#   (2,6) r  DRAIN: seq 3+4=7   drain 0+4=4
# SEQ enters the WEST wall at local row 2; DRAIN the SOUTH wall at local col 2.
# (A pipe cell with a room wall on BOTH sides is a load error -- that is why the
#  drain approaches from below instead of squeezing up the column between the
#  checker's east wall and the reader's west wall.)
SEQ_ROW, DRAIN_COL = 2, 2


def emit_checker_tight(L, cx, cy):
    """West wall at column cx, north wall at row cy.
    Interior columns cx+1..cx+6, rows cy+1..cy+9.  Room 8 wide x 11 tall."""
    x = lambda i: cx + i
    y = lambda j: cy + 1 + j

    # ---- overflow gadget : BOTH off>=16 exits of X get their own `1 N s` ----
    for j in (0, 1):                       # row0 = X straight (off==16)
        L.put(x(4), y(j), '1')             # row1 = X clockwise (off>16)
        L.put(x(5), y(j), 'N')
        L.put(x(6), y(j), 's')             # -1 out; walking into the east wall
    L.put(x(3), y(0), '>')                 # after the final output is free

    # ---- seq body ----
    L.put(x(3), y(1), 'X')
    L.put(x(2), y(1), 'v')                 # X counter-clockwise (off<=15) = normal
    L.put(x(3), y(2), '-')                 # A = seq - (W+16)
    L.put(x(3), y(3), 'r')                 # A = seq      [SEQ]

    # ---- poll ring ----
    L.put(x(1), y(4), '>')
    L.put(x(2), y(4), 'q')                 # [SEQ]
    L.put(x(3), y(4), 'a')                 # BP>0 -> CCW(E->N) = seq body
    L.put(x(4), y(4), 'v')
    L.put(x(4), y(5), '<')
    L.put(x(3), y(5), 'q')                 # [DRAIN]
    L.put(x(2), y(5), 'a')                 # BP>0 -> CCW(W->S) = drain body
    L.put(x(1), y(5), '^')

    # ---- drain body ----
    L.put(x(2), y(6), 'r')                 # A = val      [DRAIN]
    L.put(x(2), y(7), 's')                 # -> output
    L.put(x(2), y(8), '>')
    L.put(x(3), y(8), '1')
    L.put(x(4), y(8), '^')
    L.put(x(4), y(7), '+')                 # A = 1 + (W+16)
    L.put(x(4), y(6), 'M')                 # B = W+17

    # ---- startup: B = 16, then join the ring at its (4,5) corner ----
    L.put(x(5), y(8), '@')
    L.put(x(6), y(8), '^')
    L.put(x(6), y(7), '4')
    L.put(x(6), y(6), 'M')
    L.put(x(6), y(5), '1')
    L.put(x(6), y(4), '{')                 # A = 1<<4 = 16
    L.put(x(6), y(3), 'M')                 # B = 16
    L.put(x(6), y(2), '<')
    L.put(x(5), y(2), 'v')
    L.put(x(5), y(5), '<')                 # glides y3,y4 then west into the ring

    L.room(cx, cy, 8, 11)
    return {'seqW':  (cx - 1,        y(SEQ_ROW)),
            'drainS': (x(DRAIN_COL), cy + 11),
            'outS':   (x(5),         cy + 11)}
