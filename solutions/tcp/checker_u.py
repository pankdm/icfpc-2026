"""U-dispatch checker: 9 wide x 12 tall, no polling loop at all.

sweep8/11/12's checker is a POLLING loop: `q`+`d` on the drain pipe, `q`+`d` on
the seq pipe, and a 15-row climb between the seq poll (bottom) and the seq
service (top).  Measured on sweep11 that is 37 blank glides per packet and
~57 ticks per packet -- the critical path once the reader was fixed.

`U` replaces the whole thing.  It receives from ANY ready incoming pipe and
then faces that pipe's flow direction, so with

    seq  attached to the WEST  wall  (flows EAST  into the room)
    drain attached to the SOUTH wall (flows NORTH into the room)

one cell dispatches to two different code paths in ONE tick, and it BLOCKS when
neither pipe is ready -- exactly the idle behaviour the poll loop emulated.

Two properties that make this safe:
  * ties go to the pipe whose destination cell comes first in reading order,
    i.e. the SEQ pipe (its attach row is above the south wall).  Seq-before-
    drain is the ordering the overflow check needs: a packet with
    seq >= Wt+16 whose slot aliases Wt does get stored and drained, so `-1`+`H`
    must be reached before that bogus value is forwarded.
  * because no `r`/`q` is used any more, the nearest-INCOMING-pipe column rule
    that pinned the old checker's layout disappears entirely.

TRAP: `U` faces the man along the pipe's flow direction, and the engine derives
that from the last two PATH cells, NOT from the endpoint arrowhead.  A pipe that
runs south and then bends east into the wall makes `U` face the man SOUTH.  So
the seq pipe must approach the west wall on a straight horizontal final segment.

Registers: B = Wt (the seq being waited for), A/BP scratch.

  seq  path (east from U):  `-` off=seq-Wt | `b` `]`x4 | `d` off>=16 -> `1``N``s``H`
  drain path (north from U): `s` emit | `1` `+` `M`  -> Wt+1

  seq service 18 ticks, drain service 14 ticks   (was 38 and 19)
"""


def emit_checker_u(L, cx, cy, seq_j=2):
    """Interior x1..x7 x y1..y10; room 9 wide x 12 tall at (cx,cy).

    Returns attach hints: seqW must flow EAST into the west wall, drainS must
    flow NORTH into the south wall, out is any outgoing pipe.
    """
    x = lambda i: cx + i
    y = lambda j: cy + j

    # ---- drain path: U -> N -> s,1,+,M -> >  then down x2 and back W into U
    L.put(x(1), y(5), 's')               # emit the drained value
    L.put(x(1), y(4), '1')
    L.put(x(1), y(3), '+')               # A = 1 + Wt
    L.put(x(1), y(2), 'M')               # B = Wt+1
    L.put(x(1), y(1), '>')
    L.put(x(2), y(1), 'v')               # down x2 (through the `-` at y6: harmless, writes A)
    L.put(x(2), y(7), '<')
    L.put(x(1), y(7), '^')               # shared re-entry into U

    # ---- U ----
    L.put(x(1), y(6), 'U')

    # ---- seq path: U -> E ----
    L.put(x(2), y(6), '-')               # A = seq - Wt = off
    L.put(x(3), y(6), 'b')               # BP = off
    L.put(x(4), y(6), ']'); L.put(x(5), y(6), ']'); L.put(x(6), y(6), ']')
    L.put(x(7), y(6), 'v')
    L.put(x(7), y(7), ']')               # 4th shift -> BP = off >> 4
    L.put(x(7), y(8), 'd')               # off >= 16 -> CW (S->W) into the overflow gadget
    L.put(x(6), y(8), '1'); L.put(x(5), y(8), 'N')
    L.put(x(4), y(8), 's'); L.put(x(3), y(8), 'H')
    L.put(x(7), y(9), '<')               # ok -> west along y9 ...
    L.put(x(1), y(9), '^')               # ... and north back into U via (x1,y7)

    # ---- init ----
    L.put(x(1), y(10), '@')
    L.put(x(2), y(10), '^')              # joins the drain-return leg at (x2,y7)

    L.room(cx, cy, 9, 12)
    return {'seqW': (cx - 1, y(seq_j)),  # flows EAST into the west wall
            'drainS': (cx + 7, cy + 12), # flows NORTH into the south wall
            'north': cy - 1}
