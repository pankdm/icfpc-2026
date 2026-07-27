#!/usr/bin/env python3
"""Row occupancy of the controller: how many OP cells each row carries and the
column span they occupy.  Sparse rows are the packing opportunity -- every pair
of rows merged removes one row of box height AND one cell from every vertical
transit that crosses it.

  python3 snake3_occ.py <man> [x_lo] [x_hi]
"""
import sys

man = sys.argv[1]
xlo = int(sys.argv[2]) if len(sys.argv) > 2 else 0
xhi = int(sys.argv[3]) if len(sys.argv) > 3 else 10**9

rows = open(man).read().split("\n")
W = max(len(r) for r in rows)
rows = [r.ljust(W) for r in rows]
TURN = set("<>^v")
WALL = set("|-+=:")

tot_ops = 0
occupied = 0
print("row  ops  span      cols")
for y, r in enumerate(rows):
    cells = [x for x in range(max(0, xlo), min(W, xhi + 1))
             if r[x] != " " and r[x] not in TURN and r[x] not in WALL]
    if not cells:
        continue
    occupied += 1
    tot_ops += len(cells)
    print(f"{y:3d} {len(cells):4d}  {cells[0]:3d}-{cells[-1]:<3d} "
          f"({cells[-1] - cells[0] + 1:2d} wide)")
print(f"--- {occupied} occupied rows, {tot_ops} op cells, "
      f"mean {tot_ops / max(occupied, 1):.1f} ops/row")
