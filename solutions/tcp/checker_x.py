"""Checker with an UNCONDITIONAL overflow test: 5 wide x 14 tall, drain loop 8 ticks.

Two removals, not redistributions:

1. The overflow test was a 6-cell conditional decode -- `b` `]`x4 then `d` on
   BP>0 -- because B held Wt and the question was "is seq-Wt >= 16".  Park
   **Wt+15** in B instead and the same question is just the SIGN of `seq - B`:

       A = seq - (Wt+15)      A > 0  <=>  off >= 16

   so `-` `X` replaces `-` `b` `]`x4 `a`.  `X`'s third outcome (A == 0, i.e.
   off == 15) is an OK case here, and it rejoins the OK return with two cells.
   Seq service: 18 ticks -> 6.

2. The drain loop returned down a 5-row column.  Splitting the four ops across
   two columns (`s` `1` going north on x2, `+` `M` coming south on x1) closes the
   ring in 8 cells: U s 1 < v + M >.  That is the burst throughput limit -- the
   reader is input-starved for exactly (values x drain-loop) ticks per round --
   so 12 -> 8 is worth ~4 ticks per drained value.

B is only ever written by `M` on the drain path, and `+ - * & | ~ { } N` all
leave B alone, so the constant survives every pass a stray man makes over the
return legs.

    interior x1..x3, rows y1..y12

    init   : @ 3 v | M 5 * M  -> B = 15  (= Wt+15 with Wt = 0), then `<` into U
    drain  : U -> N  s 1 <  v + M >  -> U          (8)
    seq    : U -> S  - X                            (6 on the OK path)
             A<0 -> E ^ ^ <  -> U ;  A==0 -> S > ^  -> same return
             A>0 -> W v 1 N s H
"""


def emit_checker_x(L, cx, cy, seq_i=1, drain_i=1):
    x = lambda i: cx + i
    y = lambda j: cy + j

    # ---- init: B = 15 (3 -> M -> 5 -> * -> M), then west into U ----
    L.put(x(1), y(1), '@')
    L.put(x(2), y(1), '3')
    L.put(x(3), y(1), 'v')
    L.put(x(3), y(2), 'M')               # B = 3
    L.put(x(3), y(3), '5')               # A = 5
    L.put(x(3), y(4), '*')               # A = 15
    L.put(x(3), y(5), 'M')               # B = 15
    # (x3,y6) '<' below is shared with the seq OK-return

    # ---- drain: U -> N, ring closed across x2/x1 in 8 cells ----
    L.put(x(2), y(5), 's')               # emit the drained value
    L.put(x(2), y(4), '1')
    L.put(x(2), y(3), '<')
    L.put(x(1), y(3), 'v')
    L.put(x(1), y(4), '+')               # A = 1 + (Wt+15)
    L.put(x(1), y(5), 'M')               # B = Wt+16  (Wt advanced by one)
    L.put(x(1), y(6), '>')

    L.put(x(2), y(6), 'U')
    L.put(x(3), y(6), '<')               # shared re-entry into U

    # ---- seq: U -> S, unconditional sign test ----
    L.put(x(2), y(7), '-')               # A = seq - (Wt+15)
    L.put(x(2), y(8), 'X')               # >0 overflow (CW=W) ; <0 ok (CCW=E) ; ==0 ok (S)
    L.put(x(3), y(8), '^')               # ok (A<0)
    L.put(x(2), y(9), '>')               # ok (A==0, off == 15) rejoins
    L.put(x(3), y(9), '^')
    L.put(x(1), y(8), 'v')               # overflow
    L.put(x(1), y(9), '1'); L.put(x(1), y(10), 'N')
    L.put(x(1), y(11), 's'); L.put(x(1), y(12), 'H')

    L.room(cx, cy, 5, 14)
    return {'seqN': (x(seq_i), cy),          # pipe must flow SOUTH into the north wall
            'drainS': (x(drain_i), cy + 14), # pipe must flow NORTH into the south wall
            'nwall': cy, 'swall': cy + 13}
