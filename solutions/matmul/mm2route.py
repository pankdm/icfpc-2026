"""mm2route — BFS pipe router over the mm2 canvas.

`route()` finds a free orthogonal path between two ATTACHMENT cells (the pipe
cells just outside each room wall) and stamps the arrowheads.  `route_long()`
does the same but pads the path to a minimum length by first snaking through a
reserved rectangle -- that is how the 260+ cell A queue and B ring get their
capacity without hand-drawing a serpentine.
"""
from collections import deque
from mm2lib import VEC2ARROW, pipe

STEPS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def _free(g, p, allow):
    return p in allow or g.get(p[0], p[1]) == ' '


def bfs(g, src, dst, allow, bound):
    """Shortest free path src..dst inclusive; endpoints are always allowed."""
    x0, y0, x1, y1 = bound
    allow = set(allow) | {src, dst}
    prev = {src: None}
    q = deque([src])
    while q:
        c = q.popleft()
        if c == dst:
            path = []
            while c is not None:
                path.append(c)
                c = prev[c]
            return path[::-1]
        for dx, dy in STEPS:
            n = (c[0] + dx, c[1] + dy)
            if n in prev or not (x0 <= n[0] <= x1 and y0 <= n[1] <= y1):
                continue
            if not _free(g, n, allow):
                continue
            prev[n] = c
            q.append(n)
    return None


def route(g, src, dst, bound, end_direction=None, allow=()):
    p = bfs(g, src, dst, allow, bound)
    if p is None:
        raise ValueError(f"no route {src} -> {dst}")
    pipe(g, p, end_direction=end_direction)
    return len(p)


def snake(x0, y0, w, h, right=True, down=True):
    """Waypoints of a gapless boustrophedon filling a w x h rectangle, entering at
    (x0,y0) and running horizontally."""
    lo, hi = (x0, x0 + w - 1) if right else (x0 - w + 1, x0)
    pts = [(x0, y0)]
    d = 1 if right else -1
    y = y0
    for r in range(h):
        xe = hi if d == 1 else lo
        pts.append((xe, y))
        if r < h - 1:
            y += 1 if down else -1
            pts.append((xe, y))
            d = -d
    return pts


def route_long(g, src, dst, rect, bound, end_direction=None, lead_avoid=(), exit_avoid=()):
    """src -> [serpentine filling `rect`] -> dst.  rect = (x0, y0, w, h);
    the snake is entered at its top-left corner and left at its far end."""
    x0, y0, w, h = rect[:4]
    right = rect[4] if len(rect) > 4 else True
    body = snake(x0, y0, w, h, right=right)
    head, tail = body[0], body[-1]
    pts = body
    cells = set()
    for i in range(len(pts) - 1):
        (ax, ay), (bx, by) = pts[i], pts[i + 1]
        dx = (bx > ax) - (bx < ax)
        dy = (by > ay) - (by < ay)
        for k in range(abs(bx - ax) + abs(by - ay) + 1):
            cells.add((ax + dx * k, ay + dy * k))
    for c in cells:
        if g.get(*c) != ' ':
            raise ValueError(f"snake rect collides at {c}")
        g.put(c[0], c[1], '\x01')
    # the lead-in may enter only at the head, and must leave the exit's endpoint free
    del g.c[head]
    g.put(dst[0], dst[1], '\x01', force=True)
    avoid = [c for c in lead_avoid if g.get(*c) == ' ']
    for c in avoid:
        g.put(c[0], c[1], '\x01', force=True)
    lead = bfs(g, src, head, (), bound)
    for c in avoid:
        del g.c[c]
    del g.c[dst]
    if lead is None:
        for c in cells:
            g.c.pop(c, None)
        raise ValueError(f"no lead-in {src} -> {head}")
    g.put(head[0], head[1], '\x01', force=True)
    for c in lead:
        if c not in cells:
            g.put(c[0], c[1], '\x01', force=True)
    cells |= set(lead)          # the lead-in is not drawn yet; the exit must not cross it
    eavoid = [c for c in exit_avoid if g.get(*c) == ' ']
    for c in eavoid:
        g.put(c[0], c[1], '\x01', force=True)
    exitp = bfs(g, tail, dst, {tail}, bound)
    for c in eavoid:
        del g.c[c]
    if exitp is None:
        raise ValueError(f"no lead-out {tail} -> {dst}")
    for c in cells:
        del g.c[c]
    full = lead[:-1] + pts_expand(pts) + exitp[1:]
    pipe(g, full, end_direction=end_direction)
    return len(full)


def pts_expand(pts):
    out = []
    for i in range(len(pts) - 1):
        (ax, ay), (bx, by) = pts[i], pts[i + 1]
        dx = (bx > ax) - (bx < ax)
        dy = (by > ay) - (by < ay)
        for k in range(abs(bx - ax) + abs(by - ay)):
            out.append((ax + dx * k, ay + dy * k))
    out.append(pts[-1])
    return out
