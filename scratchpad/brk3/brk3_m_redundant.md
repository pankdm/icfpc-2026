# M -> 8 columns: the spare cells are redundant `^` in vertical runs

Column occupancy of M's 9x9 interior (56 cells):

    col 1: 8   col 2: 4   col 3: 9   col 4: 4   col 5: 3
    col 6: 7   col 7: 9   col 8: 6   col 9: 6

brk2 measured rows 4 and 9 as full at 9 cells, which is what blocks deleting a
column. Both have slack that no op-count argument sees:

* **col 8 holds `^` at y3, y4, y5, y6.** A man already heading north treats `^`
  as a no-op, so only the FIRST one he meets (y6) turns him -- **y3, y4 and y5
  are removable**, and y4 is exactly the cell that makes row 4 full.
* **col 7 holds `^` at y4 and y8.** y8 turns him north; **y4 is redundant** for
  the same reason. That is row 4's second spare.
* Plus `M`(3,9), already known redundant (B is 0 on all three chains).

So row 4 drops 9 -> 7 and row 9 drops 9 -> 8 without touching the walk or any
register, which is the precondition for a column delete.

**Sparsest column is 5, at three cells:** `W`(5,1), `M`(5,4), `0`(5,9). Deleting
it shifts cols 6-9 left one. The one that needs thought is `W`(5,1): row 1's
westward run is `<`(7) . `W`(5) `<`(4) `v`(3), the man starts blank at (6,1) and
turns west at (7,1), so after the shift `W` wants the cell the man start now
occupies. `<`(4,1) cannot take it -- column 4 carries a northbound run
(`^`(4,9), `^`(4,8), `+`(4,4)) that needs the turn at (4,1).
