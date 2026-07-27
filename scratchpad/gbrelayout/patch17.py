#!/usr/bin/env python3
"""Op dispatch: slide the whole 4-stage cascade west, next to the input read.

RE-MEASURED (the lesson): I had assumed the cascade sat at col 27 because no
column further west was free through the handler blocks.  Blankness per row
range says otherwise -- the descent lanes only have to clear the rows BETWEEN
consecutive stages:

  stage1->2 (rows 14-19) blank at 6,9,10,11,12,14,15,...
  stage2->3 (rows 21-29) blank at 4,8,9,12,13,14,18,...
  stage3->4 (rows 31-41) blank at 6,9,10,13,14

Chaining backwards from TOP (each X descends onto the next stage's `<`):

  stage4  <@9   4@8  -@7  X@6      (X unchanged; straight-west still hits TOP)
  stage3  <@12  3@11 -@10 X@9
  stage2  <@15  2@14 -@13 X@12
  stage1  <@18  1@17 -@16 X@15

so the man now leaves row 11 at col 18 instead of col 31.  That removes 13 cells
from the per-op eastward run, the 8-cell glide stage 3 used to carry between its
`-` and its X, and 12 cells from each of stage 1's and stage 2's straight-west
runs to their handlers.

Note BP is NOT needed: the cascade's position was never constrained by holding
the op in B -- it was constrained by the descent lanes, and those were free.
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


def clr(x, y, expect):
    assert rows[y][x] == expect, "expected %r at (%d,%d), got %r" % (expect, x, y, rows[y][x])
    rows[y][x] = " "


def stage(row, old, new, digit):
    """old/new = (x_entry, x_digit, x_minus, x_X); X kept if unchanged."""
    for x, ch in zip(old, ("<", digit, "-", "X")):
        if rows[row][x] == ch:
            clr(x, row, ch)
    for x, ch in zip(new, ("<", digit, "-", "X")):
        if rows[row][x] != ch:
            put(x, row, ch)


# row 11: leave east at col 18, not col 31
clr(31, 11, "v"); put(18, 11, "v")

stage(13, (31, 29, 28, 27), (18, 17, 16, 15), "1")
stage(20, (27, 26, 25, 24), (15, 14, 13, 12), "2")
stage(30, (24, 23, 22, 13), (12, 11, 10, 9), "3")
stage(42, (13, 12, 11, 6), (9, 8, 7, 6), "4")

open(dst, "w").write("\n".join("".join(r).rstrip() for r in rows))
print("wrote", dst)
