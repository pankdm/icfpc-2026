import os
import sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'solutions', 'matmul'))
sys.path.insert(0, HERE)
import t_merge as T                                  # noqa: E402
import prooms as P                                   # noqa: E402
from mm2lib import Grid                              # noqa: E402
from collections import deque                        # noqa: E402

g = Grid()
rects = []
g.room(0, 0, 3, 3); g.put(1, 1, 'I'); rects.append((0, 0, 3, 3))
d = P.dist(g, 0, 20); rects.append((0, 20, 15, 9))
ma = P.mctl(g, 0, 60, 'M', True); rects.append((0, 60, 11, 7))
mc = P.mctl(g, 0, 90, 'K', False); rects.append((0, 90, 11, 7))
ad = P.admx(g, 60, 0); rects.append((60, 0, 17, 15))
resv = P.interiors(g, rects)
resv += P.room_halo(g, rects, {(4, 29), (67, -1)})
for c in ((4, 29), (67, -1), (4, 30), (67, -2)):
    if g.get(*c) == '\x01':
        del g.c[c]
seen = {(4, 30)}
q = deque([(4, 30)])
while q:
    c = q.popleft()
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        n = (c[0] + dx, c[1] + dy)
        if n in seen or not (-40 <= n[0] <= 280 and -40 <= n[1] <= 130):
            continue
        if g.get(*n) != ' ':
            continue
        seen.add(n)
        q.append(n)
print("reachable", len(seen), (67, -2) in seen, (67, -1) in seen)
print("get(67,-2)", repr(g.get(67, -2)), "get(67,-1)", repr(g.get(67, -1)))
xs = [p[0] for p in seen]; ys = [p[1] for p in seen]
print("bbox", min(xs), max(xs), min(ys), max(ys))
