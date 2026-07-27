#!/usr/bin/env python3
"""Handler-return rail: climb at col 12 instead of riding out to col 36.

Every op handler returns to the dispatch's op-count read at (11,8) by running
east along row 19 to col 36, climbing 12 rows, then running back west along row
7 and row 8 -- 74 cells for GET, 95 for AVG.  The read is band-locked to cols
6-11, but nothing pins the climb: col 12 is blank all the way from row 18 to row
9, and row 8 is already the dispatch's westbound lane, so a `<` there is a
redundant turn for the traffic already on it.

    (12,19)^  ->  col 12 up  ->  (12,8)<  ->  (11,8)r

MEASURED blank columns for a row-19-to-row-8 climb: 12, 14, 19-27, 29, 36, 37.
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


put(12, 19, "^")
put(12, 8, "<")

open(dst, "w").write("\n".join("".join(r).rstrip() for r in rows))
print("wrote", dst)
