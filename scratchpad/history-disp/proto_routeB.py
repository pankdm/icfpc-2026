#!/usr/bin/env python3
"""Route-B dispatcher: worked-out arithmetic, and a partial floor plan.

*** STATUS: the arithmetic below is verified.  The floor plan is NOT -- three
*** routing conflicts are still open, listed at the bottom.  The shipped
*** dispatcher remains build_ring.disp_compact_rows() (21x5).

Run this file to print the register trace and the open issues.

WHAT ROUTE B HAS TO CLASSIFY
----------------------------
Threshold stays 17 and ESC stays 29; two runs of otherwise-dead symbol values
become one-symbol dictionary references instead of two-symbol escape pairs:

    v == 0            -> forward to YEAR
    1 <= v <= 16      -> ring position v
    v == 17           -> reserved, never occurs
    v == 29           -> ESC, the next symbol is the ring position
    19 <= v <= 22     -> ring position v - 2      (recycled run A)
    60 <= v <= 65     -> ring position v - 39     (recycled run B)
    otherwise         -> literal byte v + 31

That is 19 direct entries instead of 9, 1926 stream symbols instead of 2042,
and a 60-row feeder instead of 64 -- height 78 at width 80, i.e. 6400 with two
rows of slack.

THE THREE THINGS THAT MAKE IT FIT
---------------------------------
1. Products, not comparisons.  A two-sided range test needs two constants while
   A and B are both live and BP is write-only.  A product needs one:

       (18-v)(23-v) < 0  <=>  19 <= v <= 22
       (59-v)(66-v) < 0  <=>  60 <= v <= 65

   Both factors derive from one accumulator, and each product's two zeros
   (v = 18, 23 and v = 59, 66) are used byte symbols, so X's straight branch
   sends them to the literal-byte path where they already belonged.

2. The `-` at row 2 x9 is free work.  It is the classifier's -17 descent cell
   and cannot move -- it has to sit between the head's X and the 3-way X on the
   same column.  But the byte path also crosses it travelling east, carrying
   B = v, so loading 18 first makes that cell compute 18-v at no cost.  This is
   why the factors are written (18-v)(23-v) rather than (v-18)(v-23).

3. BP is untouched by all of it.  The head's `b` leaves BP = v and no A/B
   arithmetic disturbs it, so run A's position is just `m` `m`.  Only run B,
   whose offset is 39, has to rebuild BP from B.
"""
from __future__ import annotations

# --- the arithmetic, checked exhaustively -----------------------------------

def classify(v):
    """Mirror of the intended cell sequence, register by register."""
    A, B, BP = 17, 17, 0            # head: `17` then M
    A = v                           # r
    BP = v                          # b
    if A == 0:
        return ("year", 0)
    A = A - B                       # r2 x9 `-`   (A = v-17)
    if A < 0:
        return ("ring", BP)         # v <= 16, BP already v
    if A == 0:
        return ("reserved", None)
    A = A + B                       # `+`  A = v
    B = A                           # `M`  B = v
    A = 29                          # `92` read westward
    A = A ^ B                       # `~`
    if A == 0:
        return ("esc", None)
    # ---- byte path, test A ----
    A = 18                          # `18` read eastward, B = v survives
    A = A - B                       # the free `-` at r2 x9      A = 18-v
    B = A                           # `M`
    A = 5                           # `5`
    A = A + B                       # `+`                        A = 23-v
    A = A * B                       # `*`     A = (23-v)(18-v),  B = 18-v
    if A < 0:
        BP = BP - 1; BP = BP - 1    # `m` `m`                    BP = v-2
        return ("ring", BP)
    # ---- test B ----
    A, B = B, A                     # `W`     A = 18-v
    B = A                           # `M`
    A = 41                          # `14` read westward
    A = A + B                       # `+`                        A = 59-v
    B = A                           # `M`
    A = 7                           # `7`
    A = A + B                       # `+`                        A = 66-v
    A = A * B                       # `*`     A = (66-v)(59-v),  B = 59-v
    if A < 0:
        A, B = B, A                 # `W`     A = 59-v
        B = A                       # `M`
        A = 20                      # `02` read westward
        A = A - B                   # `-`                        A = v-39
        BP = A                      # `b`
        return ("ring", BP)
    A, B = B, A                     # `W`     A = 59-v
    B = A                           # `M`
    A = 90                          # `09` read westward
    A = A - B                       # `-`                        A = v+31
    return ("byte", A)


def expected(v):
    if v == 0:
        return ("year", 0)
    if v <= 16:
        return ("ring", v)
    if v == 17:
        return ("reserved", None)
    if v == 29:
        return ("esc", None)
    if 19 <= v <= 22:
        return ("ring", v - 2)
    if 60 <= v <= 65:
        return ("ring", v - 39)
    return ("byte", v + 31)


OPEN = """
OPEN ROUTING CONFLICTS  (the arithmetic is done; the floor plan is not)

The logic needs about 40 cells more than the 19 free interior cells of the
current 21x5 grid, so DISP grows to 8 content rows, and the ring machinery has
to move from rows 3/4 down to rows 6/7 -- today row 3 is full from x0 to x20,
so no column passes through it and the byte path cannot reach a new row at all.

Three placements are still unresolved.  All three are the same shape: an `X`
branches north or south into a cell that is already spoken for.

1. Test B needs 12 consecutive cells (W, M, 4-cell literal, +, M, 7, +, *, X).
   Entering from the east at x22 puts its `X` at x10 -- exactly the v<=16
   descent column.  Moving the descent to x11 only pushes the collision into
   the classify chain on row 3.

2. Test B's A>0 branch (the literal-byte case) turns north off its row.  On
   row 4 that lands in the classify chain (row 3, x0..x9) or the descent; on
   row 5 it lands in test A's tail on row 2.

3. The ESC lane (`>` `r` `b` plus its eastward corridor) and test B want the
   same span of row 5, and the ESC riser column wants the same x as test B's
   branch column.

Widening DISP is the obvious lever and it is affordable -- at 24 interior
columns the ring strip is still 4 columns x 10 band rows = 40 cells against the
38 the ring needs -- but each extra column also shifts every branch column, so
this wants to be done against simtest rather than on paper.  That is the next
step.
"""

if __name__ == "__main__":
    bad = [(v, classify(v), expected(v))
           for v in range(0, 92) if classify(v) != expected(v)]
    print(f"register trace vs spec over v = 0..91: "
          f"{'OK, no mismatches' if not bad else bad}")
    print(f"  ring positions produced: "
          f"{sorted({classify(v)[1] for v in range(92) if classify(v)[0]=='ring'})}")
    print(OPEN)
