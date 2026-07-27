#!/usr/bin/env python3
"""Swap which relay holds the subject index and which holds the batch op count.

MEASURED: R1 (in-band 6-11 / out-band 9-14) held exactly one logical value --
the subject index -- and R4 (24-28 / 27-31) held exactly the batch op count.
The subject is read once per STUDENT by AVG's and TOP's id handlers, which sit
beside their rings at cols 27-33; the op count is touched three times per OP.
So the hot value was in the far band and the cold value in the near one.

After patch8 (GET/SET carry the subject in BP) only 8 ops touched R1, all of
them AVG/TOP.  Swapping the two values moves those id handlers next to their
rings and pushes the op count west, where its own walk already goes.

Per-cell profile counts pick every destination column: each must be walked by
the op's OWN path at exactly its own count (a higher count means a foreign path
crosses and would fire the op too).  That rules out (27,36) [96 = walk + the
id-exit descent], (13,49/50) [64], (22,50) [39], (4,31) [8], (3,44)/(28,44) [9],
and cols 12/13/16 on rows 36/37.

Book-keeping: AVG/TOP finalizations used to drain the register; now their setups
drain-then-write instead (B still holds the subject, so `r W` recovers it), and
the post-roster path pre-loads one dummy so the first drain has something to take.
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


# ---- op count: R4 bands -> R1 bands --------------------------------------
clr(27, 6, "s"); put(10, 6, "s")            # batch: write O
clr(28, 7, "r")                             # per-op read moves down to row 8
clr(16, 8, "N"); clr(15, 8, "X")
put(11, 8, "r"); put(10, 8, "N"); put(9, 8, "X")
clr(15, 9, "<"); put(9, 9, "<")             # O>0 branch turns 6 cols further west
clr(28, 10, "s"); put(10, 10, "s")          # write O-1

# ---- subject: R1 bands -> R4 bands ---------------------------------------
# AVG setup: zero R2/R3 first, then drain-and-write the subject
clr(9, 31, "s"); clr(12, 31, "0")
put(3, 31, "M"); put(5, 31, "0")
put(24, 31, "r"); put(25, 31, "W"); put(27, 31, "s")

# TOP setup: same shape, after the -9999999 max seed
clr(9, 44, "s")
put(5, 44, "M")
put(24, 44, "r"); put(25, 44, "W"); put(27, 44, "s")

# AVG id handler: rebuild B=128 on the westbound row-37 leg, then r/b/s beside
# the ring.  (16,36)'1' stays -- TOP's northbound col-16 corridor executes it.
clr(8, 37, "^"); clr(8, 36, ">")
clr(9, 36, "r"); clr(10, 36, "b"); clr(11, 36, "s")
clr(14, 36, "7"); clr(15, 36, "M"); clr(17, 36, "{")
clr(22, 37, "<")
put(26, 37, "7"); put(25, 37, "M"); put(24, 37, "1"); put(23, 37, "{"); put(22, 37, "M")
put(21, 37, "^"); put(21, 36, ">")
put(24, 36, "r"); put(25, 36, "b"); put(28, 36, "s")

# the shared B=128 'M' on the ring's entry column has to go: the handler now
# arrives there with the subject in A.
clr(29, 34, "M")
# ...so the accumulator return builds B=128 entirely on row 39, ending in `W`
# (A is dead -- the ring's `r` overwrites it) and reusing `b` for the BP guard,
# which only has to exceed K.
clr(24, 39, "9"); clr(25, 39, "b"); clr(26, 39, "7"); clr(27, 39, "M"); clr(28, 39, "1")
put(23, 39, "7"); put(24, 39, "M"); put(25, 39, "1")
put(26, 39, "{"); put(27, 39, "b"); put(28, 39, "W")
clr(29, 38, "{")

# TOP id handler: W and the R2 write stay west (R2's band is 15-20), the R4
# round trip moves beside the ring.
clr(9, 49, "v"); clr(9, 50, ">")
clr(10, 50, "r"); clr(11, 50, "b"); clr(12, 50, "s"); clr(14, 50, "W")
put(12, 49, "v"); put(12, 50, ">"); put(14, 50, "W")
put(24, 50, "r"); put(25, 50, "b"); put(27, 50, "s")

# ---- book-keeping ---------------------------------------------------------
put(28, 9, "s")                             # once-per-program pre-load
clr(8, 40, "r"); clr(8, 55, "r")            # finalization drains no longer needed

open(dst, "w").write("\n".join("".join(r).rstrip() for r in rows))
print("wrote", dst)
