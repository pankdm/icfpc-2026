#!/usr/bin/env python3
"""Route-B dispatcher: worked-out arithmetic, and a partial floor plan.

*** STATUS: the arithmetic below is verified exhaustively.  The floor plan is
*** NOT -- one routing conflict is still open, described at the bottom.  The
*** shipped dispatcher remains build_ring.disp_compact_rows() (21x5).

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
FLOOR PLAN: two of three conflicts resolved, one left

The logic needs ~40 cells more than the 19 free interior cells of the current
21x5, so DISP grows to 8 content rows and 24 interior columns.  24 is the cap:
the band is 1 + 12 + 3 + 3 + 29 + 2 = 50 columns of other rooms and gaps, so
DISP's room plus the ring strip get 30, and the strip needs 4 columns to carry
38 cells over a 10-row band.

Resolved
--------
* The ring machinery moves from rows 3/4 to rows 6/7.  Today row 3 is full from
  x0 to x20, so no column passes through it and the byte path cannot reach any
  new row at all.
* The ESC lane moves to row 7, alongside the ring underside.  It then walks
  east straight into the rotate entry with no riser of its own -- the machinery
  is on the same pair of rows.  That frees row 5 completely, which is where
  test B goes, and it removes the old row-5 contention entirely.
* With the ESC lane gone from row 5, test B fits exactly: entering westward at
  x14 it is W, M, `14`(west -> 41), +, M, 7, +, *, X across x13..x2 -- 12 cells,
  and its X at x2 branches north into row 4 (free) and south into row 6 (free,
  since the ESC lane is now on row 7).

Still open
----------
The `v <= 16` descent.  It leaves the 3-way X at row 3 x9 travelling east and
has to reach the rotate entry on row 6, so it must cross rows 4 and 5 in some
column -- and every column of row 5 between x2 and x13 is now test B, while the
rotate entry itself sits in the ring machinery's 11-column span on rows 6/7.
Putting the descent right of test B collides with the machinery; putting it
left collides with test B's literal.

The machinery span, the descent column and test B's 12 cells are three
constraints on 24 columns and they do not currently co-exist.  Options not yet
tried: shorten the drain loop, split the descent so it crosses row 5 outside
x2..x13 and walks back along row 6, or give test B a 1-digit constant by
re-choosing the recycled runs (runs 19-22 + 29-31 need constants 10 and 4
instead of 41 and 7, but 10 is still two digits, so this saves nothing).
"""


if __name__ == "__main__":
    bad = [(v, classify(v), expected(v))
           for v in range(0, 92) if classify(v) != expected(v)]
    print(f"register trace vs spec over v = 0..91: "
          f"{'OK, no mismatches' if not bad else bad}")
    print(f"  ring positions produced: "
          f"{sorted({classify(v)[1] for v in range(92) if classify(v)[0]=='ring'})}")
    print(OPEN)
