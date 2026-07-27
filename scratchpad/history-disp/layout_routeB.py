#!/usr/bin/env python3
"""Route-B dispatcher floor plan: intermediate state, one conflict left.

*** NOT BUILDABLE YET.  Run it to print the grid and the open conflict.
*** The shipped dispatcher is build_ring.disp_compact_rows() (21x5).

24 interior columns x 8 rows.  24 is the cap: the service band spends
1 + 12 + 3 + 3 + 29 + 2 = 50 columns on the other rooms and their gaps, leaving
30 for DISP's room plus the ring strip, and the strip needs 4 of those to carry
38 cells over a 10-row band.

WHAT CHANGED FROM THE 21x5
--------------------------
* The ring machinery moved from rows 3/4 to rows 6/7 (x12..x22).  Today row 3
  is full from x0 to x20, so no column passes through it and the byte path
  cannot reach a new row at all.
* The ESC lane went **vertical**: `r` and `b` stack in column 0 on rows 4 and 5
  rather than lying along a row.  This is the move that unlocked everything
  else -- a horizontal ESC lane wanted a whole row plus a riser column, and it
  was contending with test B for both.
* Row 3 right of x10 and all of row 5 became blank corridors.  Blank cells are
  direction-preserving, so the same cell serves the `v <= 16` descent running
  east and the byte branches dropping south through it.

  legend   .  blank corridor (deliberately empty, walked through)
           !  CONFLICT -- two lanes want this cell
"""
from __future__ import annotations

W, H = 24, 8

ROWS = [
    #         1111111111222 2
    # 123456789012345678901 2 3
    "v@<<s  <  <             ",   # r0 corridor: `s`->YEAR at x4, landings
    ">`17`Mr bX^   >mm       ",   # r1 head; x14.. is run A's tail, BP-2
    " >`18`   -M5+*X v       ",   # r2 test A; the `-` at x9 is the free one
    "vX~`92`M+X..............v",  # r3 classify; x10..x22 corridor, x23 drops
    "r <M`41`M+7M+W<<........v",  # r4 ESC `r`; test B x2..x14; x23 drops
    "b......................<",   # r5 ESC `b`; descent walks west to x1
    "> >.........>ROTATE-----",   # r6 rotate entry x12; corridor x1..x11
    "  >W M`20`-b^  UNDERSIDE",   # r7 run B's BP rebuild, then east to x12
]

CONFLICT = """
THE ONE REMAINING CONFLICT
--------------------------
Test B's `X` sits at row 4 x2, and travelling west its two byte outcomes turn
the wrong way into occupied cells:

    A > 0  -> CW  W->N  -> row 3 x2, which is the ESC test's `~`
    A == 0 -> straight west -> row 4 x1, x0, which is the ESC lane's column

Moving test B east does not help.  It needs 12 consecutive cells
(W, M, 4-cell literal, +, M, 7, +, *, X), so entering at x23 puts the `X` at
x11 -- and then its north branch lands on row 3's descent corridor, where a
catcher cell would sweep the byte value east into the descent and on to the
rotate entry, i.e. it would be treated as a dictionary reference.

So the three things that do not co-exist on 24 columns are:

  1. test B's 12-cell run, whose `X` must have a free cell north and south;
  2. the `v <= 16` descent corridor, which occupies row 3 from x10 east and
     row 5 from x22 west, because it has to get from the classifier at row 3 x9
     down to the rotate entry at row 6 x12;
  3. the ring machinery's 11-column span on rows 6/7.

NEXT THINGS TO TRY, cheapest first
----------------------------------
a. Flip test B to run east.  Its `X` then branches CCW->N for in-range and
   CW->S for byte, swapping which outcome needs the free cell -- the byte
   outcome would fall south into row 5, which is corridor, and the in-range
   outcome north into row 3, also corridor.  Both would need catchers, but the
   byte catcher is the harmless one: it can drop to row 7 and rejoin the tail.
b. Shorten the drain loop so the machinery span goes 11 -> 9 columns, which
   buys two columns for the descent to turn in.
c. Mirror the rotate loop so it is entered from the east (`<`, ` `, `m`, `a`
   over `>`, `r`, `s`, `^`), which puts the entry next to the descent's natural
   arrival column instead of across the machinery from it.
"""

if __name__ == "__main__":
    print(f"DISP prototype, {W} interior columns x {H} rows\n")
    hdr = "".join(str(x % 10) for x in range(W))
    print(f"      {hdr}")
    for y, row in enumerate(ROWS):
        print(f"  r{y}  {row[:W]}")
    print(CONFLICT)
