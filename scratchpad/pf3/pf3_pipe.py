#!/usr/bin/env python3
"""Follow a pipe's cell path from its source, and report length + bounding box.

  python3 scratchpad/pf3/pf3_pipe.py <man> <sx> <sy>
"""
import sys

man, sx, sy = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
rows = open(man).read().split("\n")
while rows and not rows[-1].strip():
    rows.pop()
w = max(len(r) for r in rows)
rows = [r.ljust(w) for r in rows]
h = len(rows)

D = {">": (1, 0), "<": (-1, 0), "^": (0, -1), "v": (0, 1)}
PIPE = set("<>^v-|")

path = [(sx, sy)]
x, y = sx, sy
ch = rows[y][x]
assert ch in D, "source must be an arrow, got %r" % ch
dx, dy = D[ch]
seen = {(x, y)}
for _ in range(4000):
    nx, ny = x + dx, y + dy
    if not (0 <= nx < w and 0 <= ny < h):
        break
    c = rows[ny][nx]
    if c not in PIPE:
        path.append((nx, ny))
        break
    if c in D:
        dx, dy = D[c]
    x, y = nx, ny
    if (x, y) in seen:
        break
    seen.add((x, y))
    path.append((x, y))

xs = [p[0] for p in path]
ys = [p[1] for p in path]
print("length %d cells   x %d-%d   y %d-%d" % (len(path), min(xs), max(xs), min(ys), max(ys)))
print("end", path[-1], "glyph", rows[path[-1][1]][path[-1][0]])
rowsused = {}
for px, py in path:
    rowsused.setdefault(py, []).append(px)
print("rows touched:", sorted(rowsused))
for py in sorted(rowsused):
    if py >= 160:
        v = sorted(rowsused[py])
        print("   row %d: %d cells %d-%d" % (py, len(v), v[0], v[-1]))
