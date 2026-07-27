#!/usr/bin/env python3
"""Walk CTRL's serpentine on the generated grid and diff it against the op stream
swar_setup emitted.  A layout bug shows up as a divergence index; a machine bug
does not."""
import os
import sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "solutions", "plotter"))
import swar_setup as SS  # noqa: E402

MAN = os.path.join(HERE, "..", "solutions", "plotter", "plotter-swar1.man")
rows = open(MAN).read().split("\n")


def at(x, y):
    return rows[y][x] if 0 <= y < len(rows) and 0 <= x < len(rows[y]) else " "


# find the CTRL '@' : the one inside the tall room (largest y-extent room start)
starts = [(x, y) for y, r in enumerate(rows) for x, c in enumerate(r) if c == "@"]
print("men at", starts)
sx, sy = (2, 13)
print("walking from", (sx, sy))

DIRS = {">": (1, 0), "<": (-1, 0), "^": (0, -1), "v": (0, 1)}
x, y, d = sx, sy, (1, 0)
seq = []
for _ in range(4000):
    c = at(x, y)
    if c in DIRS:
        d = DIRS[c]
    elif c not in "@. ":
        seq.append(c)
    if c == "d" or c == "X":
        break
    x, y = x + d[0], y + d[1]
    if not (1 <= x <= 56 and 13 <= y <= 29):
        print("left CTRL at", (x, y), "after", len(seq), "ops")
        break

toks = [t for t, _ in SS.run(3, 4, 20, 19).toks]
print(f"grid ops {len(seq)}  emitted {len(toks)}")
for i, (a, b) in enumerate(zip(seq, toks)):
    if a != b:
        print(f"DIVERGE at {i}: grid {a!r} vs emitted {b!r}")
        print("  grid    ", "".join(seq[max(0, i - 25):i + 10]))
        print("  emitted ", "".join(toks[max(0, i - 25):i + 10]))
        break
else:
    print("prefix matches for", min(len(seq), len(toks)), "ops")
