#!/usr/bin/env python3
"""AVG's per-belt-value ring: 28 ticks -> 18.

The ring spanned cols 22-33 only because the id/grade classifier materialised
its threshold as a 5-cell HORIZONTAL literal `101` on the west leg, plus an `M`
to stash the value in B.  Instead park the threshold in B once, on the entry
path (row 36, which is walked once per student, not once per value):

    7 M 1 {  M      ->  A=7, B=7, A=1, A=1<<7=128, B=128     (no backticks)

Then the ring needs only `-` `N` (A = 128 - v; grade > 0, id < 0 -- the same
polarity the old classify X expects) and the west leg collapses from col 22 to
col 27.  The accumulator downstream needs B = v, which `M` used to supply, so
the found-target exit restores it in three cells that run once per student:

    N + M           ->  A = v-128, A = v, B = v            (B is still 128)

Threshold 128 rather than 101: any T with 100 < T <= 1000 separates grades
(<=100) from ids (>=1000), and 128 = 1<<7 costs no literal.

  ring: >_rsv_<X<v<-N_Xmd_   16 cells + the 2-tick v>0 detour = 18
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


# --- entry path (row 36, once per student): park B = 128 -------------------
for x, ch in ((14, "7"), (15, "M"), (16, "1"), (17, "{"), (18, "M")):
    put(x, 36, ch)

# --- drop the old west leg: X, -, and the `101` literal --------------------
for x, ch in ((22, "X"), (23, "-"), (24, "`"), (25, "1"), (26, "0"), (27, "1"), (28, "`")):
    clr(x, 35, ch)
clr(22, 34, "m")
clr(22, 33, "d")
clr(33, 34, "M")          # B = v is now restored on the found-exit instead

# --- new west leg ----------------------------------------------------------
put(30, 35, "-")          # A = v - 128   (also on the col-30 align corridor: harmless)
put(29, 35, "N")          # A = 128 - v   (also on the ring entry corridor: harmless)
put(27, 35, "X")          # classify: grade A>0 -> N, id A<0 -> S
put(27, 34, "m")
put(27, 33, "d")          # BP>0 -> E back to r; BP<=0 -> N to the found-exit

# --- found-target exit: restore A = v and B = v ---------------------------
put(27, 32, "<")
put(26, 32, "N")
put(25, 32, "+")
put(24, 32, "M")

# --- id exit: drop to the row-37 westbound return -------------------------
put(27, 37, "<")

open(dst, "w").write("\n".join("".join(r).rstrip() for r in rows))
print("wrote", dst)
