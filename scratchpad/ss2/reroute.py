#!/usr/bin/env python3
"""subset-sum step 1: re-serpentine the r3->r0 loop pipe out of columns 85-94.

The grid is 95x92 -> box 9025 is WIDTH-bound, and cols 85-94 are used by exactly
one thing: pipe 1 (r3 -> r0, 238 cells).  Cols 73-83 rows 11-91 are completely
empty, so the same 238 cells fit there.  Length is preserved EXACTLY -- the pipe
is a delay/capacity line and shortening it would change behaviour, not just
geometry.

New path (238 cells, head on r3's bottom wall, tail unchanged at (39,0)):
    (81,11) v                      head, back-cell (81,10) = r3 bottom wall
    row 11 west   80..73           8
    col 73 south  12..91          80
    row 91 east   74..84          11
    col 84 north  90..0           91
    row 0  west   83..84? no:     45 with a 2-cell bump at cols 82-83 for parity
The tail cell (39,0) still points south into r0's top wall, so r0's incoming
reading order and every nearest-pipe binding inside r0 are untouched.

    python3 scratchpad/ss2/reroute.py [out.man]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "teammate.man")
DST = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "ss2-reroute.man")

g = [list(l.rstrip("\n")) for l in open(SRC).read().split("\n")]
while g and not "".join(g[-1]).strip():
    g.pop()
W = max(len(r) for r in g)
for r in g:
    r += [" "] * (W - len(r))
H = len(g)

# ---- the old pipe-1 cells, recomputed the same way pipes.py traces them ----
OLD = []
p = (83, 7)
OLD.append(p)
for y in range(7, 90):
    OLD.append((84, y))
for x in range(85, 95):
    OLD.append((x, 89))
for y in range(88, -1, -1):
    OLD.append((94, y))
for x in range(93, 38, -1):
    OLD.append((x, 0))
OLD = OLD[1:] if OLD[0] == OLD[1] else OLD
seen = set()
OLD = [c for c in OLD if not (c in seen or seen.add(c))]

# ---- the new path ----
NEW = [(81, 11), (81, 12)]                           # head must step AWAY from r3
NEW += [(x, 12) for x in range(80, 72, -1)]          # west to col 73
NEW += [(73, y) for y in range(13, 92)]              # south to row 91
NEW += [(x, 91) for x in range(74, 85)]              # east to col 84
NEW += [(84, y) for y in range(90, -1, -1)]          # north to row 0
NEW += [(83, 0), (83, 1), (82, 1), (82, 0)]          # 2-cell bump (length parity)
NEW += [(x, 0) for x in range(81, 38, -1)]           # west to the unchanged tail

def main():
    assert len(set(NEW)) == len(NEW), "new path self-intersects"
    print("old cells %d  new cells %d" % (len(OLD), len(NEW)))
    if len(NEW) != len(OLD):
        raise SystemExit("LENGTH MISMATCH %d != %d" % (len(NEW), len(OLD)))
    old = set(OLD)
    for (x, y) in OLD:
        g[y][x] = " "
    for (x, y) in NEW:
        if g[y][x] != " ":
            raise SystemExit("new path hits %r at (%d,%d)" % (g[y][x], x, y))
    arr = {(1, 0): ">", (-1, 0): "<", (0, 1): "v", (0, -1): "^"}
    for i, (x, y) in enumerate(NEW):
        nxt = NEW[i + 1] if i + 1 < len(NEW) else (39, 1)
        d = (nxt[0] - x, nxt[1] - y)
        if d not in arr:
            raise SystemExit("non-unit step %s -> %s" % ((x, y), nxt))
        g[y][x] = arr[d]
    out = "\n".join("".join(r).rstrip() for r in g) + "\n"
    open(DST, "w").write(out)
    w = max(len(l) for l in out.split("\n"))
    h = len([l for l in out.split("\n") if l.strip()])
    print("wrote %s  %dx%d  box=%d" % (DST, w, h, max(w, h) ** 2))


if __name__ == "__main__":
    main()
