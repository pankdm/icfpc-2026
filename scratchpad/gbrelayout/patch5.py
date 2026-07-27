#!/usr/bin/env python3
"""Roster load: read TWO values per trip.  62 ticks/value -> 37.

The loop's two long legs are band-forced (IN is cols 1-5, belt-out is 32-37),
so the only way to shorten it is to amortise one trip over two values:

    r M r W  ...  s W s        A=v1,B=v2 -> send v1, swap, send v2

The blocker was parity: count = N*(K+1) is odd whenever N is odd and K is even,
and a pair loop would then read one value too many (the next round's op count).
Fix: the ODD final pass rides the same tail, sending [v_last, sentinel] --
`1 N W` turns (A=v,B=v) into (A=v,B=-1) in three cells without losing v, and
the tail's `s W s` then emits exactly v_last then -1.

BP distinguishes the two exits: `m` fires once per value consumed, so the even
exit leaves BP=0 and the odd exit BP=-1.  `x` (low bit of BP) routes the even
exit to the sentinel emitter and the odd exit (sentinel already sent) around it
via row 1 and col 36.

  row 3  > r M r'  1 N W >   ................  s W s v      ' = the d branch
  row 4      r          x  d m  ..............  <
  row 5      > W    ^   > 1 N   ..............  s     v
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


# --- tear down the single-value loop --------------------------------------
clr(4, 2, "v"); clr(15, 2, "<")
clr(4, 3, ">"); clr(5, 3, "r"); clr(33, 3, "v")
clr(12, 4, "v"); clr(13, 4, "N"); clr(14, 4, "1")
clr(15, 4, "d"); clr(16, 4, "m"); clr(33, 4, "<")
clr(12, 5, ">")

# --- row 3: read v1, branch, read-pair tail -------------------------------
for x, ch in ((1, ">"), (2, "r"), (3, "M"), (4, "m"), (5, "d"),
              (6, "1"), (7, "N"), (8, "W"), (9, ">"),
              (33, "W"), (34, "s"), (35, "v")):
    put(x, 3, ch)

# --- row 4/5: the second read and the rejoin ------------------------------
put(5, 4, "r")            # col 5 is the east edge of the IN band
put(35, 4, "<")
put(5, 5, ">")
put(6, 5, "W")            # A=v1, B=v2
put(9, 5, "^")            # rejoin row 3 east of the odd-only cells

# --- row 4: second decrement, loop test, parity test ----------------------
put(17, 4, "m")
put(16, 4, "d")           # BP>0 -> N, back round the loop
put(14, 4, "x")           # BP=0 even -> S (emit sentinel), BP=-1 odd -> N

# --- row 2: the westbound return ------------------------------------------
put(16, 2, "<")
put(1, 2, "v")

# --- even exit: set A=-1 and reuse the row-5 belt send --------------------
put(14, 5, ">")
put(15, 5, "1")
put(16, 5, "N")

# --- odd exit: skip the sentinel emitter, rejoin the post-roster column ---
put(14, 1, ">")
put(36, 1, "v")
put(36, 6, "<")
put(35, 6, "v")           # even arrives from the north, odd from the east

open(dst, "w").write("\n".join("".join(r).rstrip() for r in rows))
print("wrote", dst)
