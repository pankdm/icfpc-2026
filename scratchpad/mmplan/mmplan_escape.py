#!/usr/bin/env python3
"""Which engine room walls box in ENG.IN / ENG.OUT, and by how much?

reach3 established that neither port escapes the engine bbox. That is a
yes/no. For a floorplan what matters is WHICH rooms form the boundary of the
reachable pocket and how far each would have to move to open a channel -- that
turns "cannot be reused" into a costed modification.

Clearance rule (measured): a pipe may hug a foreign ROOM WALL; it may only not
touch another PIPE, since two adjacent pipes parse as one.
"""
import os, sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'solutions', 'matmul'))
sys.path.insert(0, os.path.join(REPO, 'scratchpad', 'mmpar'))
sys.path.insert(0, os.path.join(REPO, 'tools'))
from mm2lib import Grid                      # noqa: E402
import build_e1 as E                         # noqa: E402
import router as RT                          # noqa: E402

g = Grid()
rm, inp, out = E.engine(g, 0, 0, io=False)
occ = {c for c, ch in g.c.items() if ch != ' '}
typ = g.R.grid.typ if hasattr(g, 'R') else {}
pipes = {c for c in occ if typ.get(c) == RT.PIPE}
blocked = set(occ)
for (x, y) in pipes:                          # pipes only get a halo
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        blocked.add((x + dx, y + dy))

xs = [c[0] for c in occ]; ys = [c[1] for c in occ]
X0, X1, Y0, Y1 = min(xs) - 3, max(xs) + 3, min(ys) - 3, max(ys) + 3
print(f'engine bbox x[{min(xs)},{max(xs)}] y[{min(ys)},{max(ys)}]')

# map every occupied cell to the room that owns it, for boundary attribution
owner = {}
for name, r in rm.items():
    try:
        x, y, w, h = r.x, r.y, r.w, r.h
    except AttributeError:
        continue
    for i in range(w):
        for j in range(h):
            owner[(x + i, y + j)] = name


def probe(start, label):
    if start in blocked:
        print(f'{label}: start {start} is itself blocked'); return
    seen, q = {start}, deque([start])
    escaped = False
    while q:
        c = q.popleft()
        if not (X0 <= c[0] <= X1 and Y0 <= c[1] <= Y1):
            escaped = True
            continue
        for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (c[0] + d[0], c[1] + d[1])
            if n in seen or n in blocked:
                continue
            seen.add(n); q.append(n)
    bx = [c[0] for c in seen]; by = [c[1] for c in seen]
    print(f'\n{label}: {"ESCAPES" if escaped else "SEALED"}  pocket={len(seen)} cells  '
          f'x[{min(bx)},{max(bx)}] y[{min(by)},{max(by)}]')
    # which occupied cells form the pocket's wall, and who owns them
    wall = {}
    for c in seen:
        for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (c[0] + d[0], c[1] + d[1])
            if n in occ:
                wall[n] = owner.get(n, 'PIPE/other')
    tally = {}
    for n, o in wall.items():
        tally[o] = tally.get(o, 0) + 1
    print('  pocket boundary owners:',
          dict(sorted(tally.items(), key=lambda kv: -kv[1])[:8]))
    # nearest escape: min distance from any pocket cell to outside the bbox
    best = None
    for c in seen:
        d = min(c[0] - min(xs), max(xs) - c[0], c[1] - min(ys), max(ys) - c[1])
        if best is None or d < best[0]:
            best = (d, c)
    print(f'  closest pocket cell to the bbox edge: {best[1]}, {best[0]} cells of '
          f'occupied material in the way')


probe(inp, 'ENG.IN ' + str(inp))
probe(out, 'ENG.OUT ' + str(out))
