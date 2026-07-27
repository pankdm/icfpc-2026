"""Emit solutions/sort-numbers/build_r12.py reproducing a produced 12x12 .man."""
import sys
man, out = sys.argv[1], sys.argv[2]
rows = [r for r in open(man).read().split('\n')]
H = max(i for i, r in enumerate(rows) if r.strip()) + 1
W = max(len(r) for r in rows)
def at(x, y):
    return rows[y][x] if y < len(rows) and x < len(rows[y]) else ' '
rooms = []
for y0 in range(H):
    for x0 in range(W):
        if at(x0, y0) != '+': continue
        x1 = x0 + 1
        while at(x1, y0) == '-': x1 += 1
        if x1 <= x0 + 1 or at(x1, y0) != '+': continue
        y1 = y0 + 1
        while at(x0, y1) == '|': y1 += 1
        if y1 <= y0 + 1 or at(x0, y1) != '+': continue
        if at(x1, y1) != '+': continue
        if not (all(at(x, y1) == '-' for x in range(x0 + 1, x1))
                and all(at(x1, y) == '|' for y in range(y0 + 1, y1))): continue
        rooms.append((x0, y0, x1, y1))
wall = set()
for (x0, y0, x1, y1) in rooms:
    for x in range(x0, x1 + 1):
        wall.add((x, y0)); wall.add((x, y1))
    for y in range(y0, y1 + 1):
        wall.add((x0, y)); wall.add((x1, y))
cells = [(x, y, at(x, y)) for y in range(H) for x in range(W)
         if at(x, y) != ' ' and (x, y) not in wall]
src = '''#!/usr/bin/env python3
"""sort-numbers, 12x12 -> box 144.  Found by the exhaustive floorplan search in
scratchpad/sort12/ (drive5.py + search.py); the main room's control flow is
documented in scratchpad/sort12/main5.py.

Main room interior is 8 wide x 5 tall (70 cells) instead of the 8x7 the 13x13
champion used; that is what makes the four rooms plus a 16-cell return pipe fit
inside 144 cells.  Two geometry facts the search had to respect:
  * the main->relay pipe must stay short -- `q` reads the circulating count only
    ~11 ticks after the lap's last send, and the relay adds up to 6 more;
  * the relay->main return pipe alone must hold n-1 = 15 values, because lap 1
    reads from the input pipe and never drains the return pipe.
"""
import os
import sys

W = H = %d
ROOMS = %r
CELLS = %r

g = [[" "] * W for _ in range(H)]


def put(x, y, ch):
    if g[y][x] != " ":
        raise SystemExit("collision at (%%d,%%d)" %% (x, y))
    g[y][x] = ch


for x0, y0, x1, y1 in ROOMS:
    for x in range(x0, x1 + 1):
        put(x, y0, "-" if x0 < x < x1 else "+")
        put(x, y1, "-" if x0 < x < x1 else "+")
    for y in range(y0 + 1, y1):
        put(x0, y, "|")
        put(x1, y, "|")
for x, y, ch in CELLS:
    put(x, y, ch)

out = "\\n".join("".join(r).rstrip() for r in g) + "\\n"
dest = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "r12.man")
open(dest, "w").write(out)
''' % (max(W, H), rooms, cells)
open(out, 'w').write(src)
print('wrote', out, 'rooms', len(rooms), 'cells', len(cells))
