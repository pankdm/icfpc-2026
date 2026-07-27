#!/usr/bin/env python3
"""GET and SET: carry the subject index in BP instead of round-tripping it through R1.

Both ops store the subject in R1 at setup and read it back after the id scan,
purely to survive the scan.  But nothing on the scan path touches BP: the id
ring is `r s ~ X` plus turns, and ALIGN is `r s X` plus turns.  So `b` at setup
carries it directly, and the read-back plus its `b` disappear.

  GET  row 14: r(id) M r(subject) s@9->R1   row 15: ... r@11 b@10 ...
       ->      r(id) M r(subject) b@5        row 15: ... (both gone)
  SET  row 21: r(id) M r(subject) s@9->R1   row 26: > r@8 b@9 ...
       ->      r(id) M r(subject) b@6        row 26: > (both gone)

This is also the first half of freeing R1 entirely for the subject-vs-op-count
band swap: it takes R1's op count from 12 down to 8.
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


# GET: subject is read at (4,14); park it in BP right there.
clr(9, 14, "s"); put(5, 14, "b")
clr(11, 15, "r"); clr(10, 15, "b")

# SET: subject is read at (5,21).
clr(9, 21, "s"); put(6, 21, "b")
clr(8, 26, "r"); clr(9, 26, "b")

open(dst, "w").write("\n".join("".join(r).rstrip() for r in rows))
print("wrote", dst)
