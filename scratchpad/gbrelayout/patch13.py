#!/usr/bin/env python3
"""TOP's ring: 30 ticks -> 18.  The six pieces, moved atomically.

The circular blocker is gone: patch12 killed the col-22/col-28 climb, so
(22,49)'>' and (28,49)'^' now have walk count 0 and row 49 is a clear westbound
lane.  That frees the classify X to leave col 21.

  1 threshold  `7 M { M` -> A = 7<<7 = 896, B parked (896 is in the gap between
                grades <=100 and ids >=1000, and costs four cells, not five).
                Parked once per TOP op at the setup; ALIGN has no B op so it
                survives.  Needs one more column than row 44 had free, so ALIGN
                shifts one column east (r 33->34, s 34->35: both still inside
                the belt bands 29-37 / 32-37).
  2 X/m/d      col 21 -> col 27; the ring's west leg becomes `- N X`.
  3 id exit    X south to (27,49), then west down the now-empty row 49.
  4 found exit d north to (27,45), then `N + M` restores B=v for the *16384.
  5 col-22 climb  already dead.
  6 B rebuild  the id handler preserves B once its `W` becomes `N +` (W would
                swap the parked constant out), so only the two max-update
                returns rebuild -- and each has exactly the five cells needed
                once `9 b` collapses to `b` on A=896.  Nothing is placed on the
                col-30 trunk (30,47..49), which all three entries share.

Every destination column was checked against the profiler: its walk count must
equal the op's own path count (30,48)=224 and (13,49/50)=64 are shared, so they
stay glides.
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


# --- 1a. shift ALIGN one column east, freeing row 44 cols 28-31 ------------
clr(31, 43, ">"); clr(33, 43, "r"); clr(34, 43, "s"); clr(35, 43, "v")
put(33, 43, ">"); put(34, 43, "r"); put(35, 43, "s"); put(36, 43, "v")
clr(31, 44, "^"); clr(32, 44, "X"); clr(35, 44, "<")
put(32, 44, "^"); put(33, 44, "X"); put(36, 44, "<")
put(33, 45, "<")                      # sentinel exit rejoins (32,45)'<'

# --- 1b. park B = 7<<7 = 896 at the TOP setup ------------------------------
put(28, 44, "7"); put(29, 44, "M"); put(30, 44, "{"); put(31, 44, "M")

# --- 2. ring: drop M/literal, classify moves to col 27 --------------------
clr(33, 47, "M")
for x, ch in ((21, "X"), (22, "-"), (23, "`"), (24, "1"),
              (25, "0"), (26, "1"), (27, "`")):
    clr(x, 48, ch)
clr(21, 47, "m"); clr(21, 46, "d")
put(29, 48, "-"); put(28, 48, "N"); put(27, 48, "X")
put(27, 47, "m"); put(27, 46, "d")

# --- 3. id exit: row 49 is clear now --------------------------------------
clr(22, 49, ">"); clr(28, 49, "^")
put(27, 49, "<")                      # the descent must turn west, not fall through

# --- 4. found exit: restore B = v for the *16384 --------------------------
put(27, 45, "<"); put(26, 45, "N"); put(25, 45, "+"); put(24, 45, "M")

# --- 6a. id handler: N + instead of W, so the parked B survives -----------
clr(16, 50, "W"); clr(17, 50, "s")
put(16, 50, "N"); put(17, 50, "+"); put(18, 50, "s")

# --- 6b. rebuild B on the two max-update returns --------------------------
clr(26, 53, "9"); clr(27, 53, "b")                      # new-max
put(26, 53, "7"); put(27, 53, "M"); put(28, 53, "{")
put(29, 53, "b"); put(30, 52, "M")
clr(25, 51, "9"); clr(26, 51, "b")                      # not-a-new-max
put(25, 51, "7"); put(26, 51, "M"); put(27, 51, "{")
put(28, 51, "b"); put(29, 51, "M")

open(dst, "w").write("\n".join("".join(r).rstrip() for r in rows))
print("wrote", dst)
