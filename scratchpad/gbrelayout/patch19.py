#!/usr/bin/env python3
"""GET's and SET's found-path U-turns: pivot at col 30, not col 7.

After the id ring matches, both handlers sweep west across the whole room to
col 7, turn down two rows, and sweep back east to col 30/33 to reach their
grade-walk ring.  TRACED: there is not a single op on either sweep -- it is a
pure U-turn, ~55 cells of travel to move two rows down.

  GET  (31,15) west to (7,15)v (7,17)> east to (30,17)>   ->  (30,15)v (30,17)>
  SET  (31,24) west to (7,24)v (7,26)> east to (33,26)v   ->  (30,24)v (30,26)>

The pivot cells carry the found path's own count (6) and nothing else.
-47 cells x6 each = -558 ticks.
"""
import sys

src, dst = sys.argv[1], sys.argv[2]
rows = [list(r) for r in open(src).read().split("\n")]
w = max(len(r) for r in rows)
for r in rows:
    r.extend(" " * (w - len(r)))


def put(x, y, ch):
    assert rows[y][x] == " ", "occupied (%d,%d)=%r" % (x, y, rows[y][x])
    rows[y][x] = ch


put(30, 15, "v")        # GET: drop straight onto its grade-walk row
put(30, 24, "v")        # SET: same
put(30, 26, ">")        # SET's grade walk starts at (33,26), so head back east

# batch start: drop to the dispatch lane at col 12 instead of riding to col 30,
# up to row 7 and back west (-36 cells x4)
put(12, 6, "v")
# (a col-27 climb for SET's return was tried here and breaks every case -- the
# column is blank but carries traffic the blankness test cannot see.)

open(dst, "w").write("\n".join("".join(r).rstrip() for r in rows))
print("wrote", dst)
