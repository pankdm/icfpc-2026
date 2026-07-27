"""Is the dense engine's ACC.OUT port reachable from outside the block?
(with a 1-cell halo around every existing glyph, which pipes require)."""
import os
import sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import engine                                       # noqa: E402

g, _, _ = engine.build(ports=True)
occ = {c for c, ch in g.c.items() if ch != ' '}
blocked = set(occ)
for (x, y) in occ:
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        blocked.add((x + dx, y + dy))
xs = [c[0] for c in occ]
ys = [c[1] for c in occ]
x0, x1, y0, y1 = min(xs) - 12, max(xs) + 12, min(ys) - 12, max(ys) + 12

for name, port in engine.PORTS.items():
    seen = set()
    q = deque()
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        n = (port[0] + dx, port[1] + dy)
        if n not in occ:
            seen.add(n)
            q.append(n)
    out = False
    while q:
        c = q.popleft()
        if not (min(xs) <= c[0] <= max(xs) and min(ys) <= c[1] <= max(ys)):
            out = True
            break
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (c[0] + dx, c[1] + dy)
            if n in seen or not (x0 <= n[0] <= x1 and y0 <= n[1] <= y1):
                continue
            if n in blocked:
                continue
            seen.add(n)
            q.append(n)
    print(f"{name} port {port}: escapes block = {out}  (region {len(seen)} cells)")
