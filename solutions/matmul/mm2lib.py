"""mm2lib — grid helpers for the mm2 matmul engine.

Idioms used everywhere:

  LOOP BOX (`box`): a rectangular racetrack, 2 rows tall, walked clockwise.
      (x0,y0)='>'  ops...  (x1,y0)='v'
      (x0,y1)=exit ops...  (x1,y1)='<'
    entered at (x0-1,y0) heading E, so the first op executed is (x0+1,y0).
    op slots in execution order: (x0+1..x1-1, y0) then (x1-1..x0+1, y1).

  Counted variants put 'd' at a corner: 'd' entered heading W at (x0,y1)
  continues the lap when BP>0 (CW -> N) and exits west when BP==0.
  A DOUBLE-checked box also puts 'd' at (x1,y0) (entered heading E: CW -> S
  continues, BP==0 exits east) so a lap may carry two counted iterations.

  NEAREST-PIPE: `resolve()` reproduces the spec rule (Manhattan to the pipe
  cell just outside the wall, reading-order ties) so a layout can be *checked*
  instead of reasoned about.
"""

DIRS = {"E": (1, 0), "W": (-1, 0), "N": (0, -1), "S": (0, 1)}


class Grid:
    """Sparse char canvas with collision detection."""

    def __init__(self):
        self.c = {}

    def put(self, x, y, ch, force=False):
        if not force and (x, y) in self.c and self.c[(x, y)] != ch and self.c[(x, y)] != ' ':
            raise ValueError(f"collision at ({x},{y}): {self.c[(x,y)]!r} vs {ch!r}")
        self.c[(x, y)] = ch

    def get(self, x, y):
        return self.c.get((x, y), ' ')

    def text(self, x, y, s, d="E"):
        dx, dy = DIRS[d]
        for i, ch in enumerate(s):
            if ch != '\0':
                self.put(x + i * dx, y + i * dy, ch)

    def room(self, x, y, w, h):
        for i in range(w):
            self.put(x + i, y, '-')
            self.put(x + i, y + h - 1, '-')
        for j in range(h):
            self.put(x, y + j, '|', force=True)
            self.put(x + w - 1, y + j, '|', force=True)
        for cx, cy in ((x, y), (x + w - 1, y), (x, y + h - 1), (x + w - 1, y + h - 1)):
            self.put(cx, cy, '+', force=True)
        return Room(x, y, w, h)

    def render(self):
        pts = [p for p, ch in self.c.items() if ch != ' ']
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        rows = ["".join(self.get(x, y) for x in range(x0, x1 + 1)).rstrip()
                for y in range(y0, y1 + 1)]
        return "\n".join(rows)

    def footprint(self):
        pts = [p for p, ch in self.c.items() if ch != ' ']
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        w, h = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
        return w, h, max(w, h) ** 2


class Room:
    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.pipes = {}          # name -> (ax, ay, 'in'|'out')
        self.walls = {}          # name -> the border cell the pipe attaches to

    @property
    def x1(self):
        return self.x + self.w - 1

    @property
    def y1(self):
        return self.y + self.h - 1

    def attach(self, name, side, off, kind):
        """Register a pipe attachment. `off` is the coordinate along the wall.
        Returns (attach_cell, wall_cell): the pipe's endpoint sits OUTSIDE the wall."""
        if side == 'T':
            wall, att = (off, self.y), (off, self.y - 1)
        elif side == 'B':
            wall, att = (off, self.y1), (off, self.y1 + 1)
        elif side == 'L':
            wall, att = (self.x, off), (self.x - 1, off)
        elif side == 'R':
            wall, att = (self.x1, off), (self.x1 + 1, off)
        else:
            raise ValueError(side)
        self.pipes[name] = (att[0], att[1], kind)
        self.walls[name] = wall
        return att, wall

    def resolve(self, x, y, kind):
        """Which pipe does an `r`/`s` at (x,y) lock onto? Returns (name, strict)."""
        cands = [(abs(x - ax) + abs(y - ay), ay, ax, n)
                 for n, (ax, ay, k) in self.pipes.items() if k == kind]
        cands.sort()
        if not cands:
            return None, False
        best = cands[0]
        strict = len(cands) == 1 or cands[1][0] > best[0]
        return best[3], strict

    def check(self, want):
        """want: {(x,y): (name, 'in'|'out')}. Raises on any mismatch or tie."""
        bad = []
        for (x, y), (name, kind) in want.items():
            got, strict = self.resolve(x, y, kind)
            if got != name or not strict:
                bad.append(f"({x},{y}) wants {name} got {got} strict={strict}")
        if bad:
            raise ValueError("pipe binding failure:\n  " + "\n  ".join(bad))


def box(g, x0, y0, x1, ops, d_west=False, d_east=False):
    """Lay a 2-row racetrack (rows y0,y0+1) with `ops` in execution order.
    Returns dict of op-name -> (x,y) for every slot (list index)."""
    y1 = y0 + 1
    slots = [(x, y0) for x in range(x0 + 1, x1)] + [(x, y1) for x in range(x1 - 1, x0, -1)]
    if len(ops) != len(slots):
        raise ValueError(f"box {x0}..{x1}: {len(slots)} slots, {len(ops)} ops")
    g.put(x0, y0, '>')
    g.put(x1, y0, 'd' if d_east else 'v')
    g.put(x1, y1, '<')
    g.put(x0, y1, 'd' if d_west else '^')
    for (x, y), ch in zip(slots, ops):
        g.put(x, y, ch)
    return slots


def serp(x0, y0, width, rows, down=True):
    """Waypoints of a gapless boustrophedon starting at (x0,y0) heading E."""
    pts = [(x0, y0)]
    y, d = y0, 1
    step = 1 if down else -1
    for r in range(rows):
        xe = x0 + width - 1 if d == 1 else x0
        pts.append((xe, y))
        if r < rows - 1:
            y += step
            pts.append((xe, y))
            d = -d
    return pts


def serp_len(width, rows):
    return width * rows


VEC2ARROW = {(1, 0): '>', (-1, 0): '<', (0, 1): 'v', (0, -1): '^'}


def pipe(g, points, end_direction=None):
    cells = []
    for i in range(len(points) - 1):
        (ax, ay), (bx, by) = points[i], points[i + 1]
        dx = (bx > ax) - (bx < ax)
        dy = (by > ay) - (by < ay)
        for k in range(abs(bx - ax) + abs(by - ay)):
            cells.append((ax + dx * k, ay + dy * k, dx, dy))
    lx, ly = points[-1]
    cells.append((lx, ly, cells[-1][2], cells[-1][3]))
    if end_direction:
        dx, dy = DIRS[end_direction]
        cells[-1] = (lx, ly, dx, dy)
    for i, (x, y, dx, dy) in enumerate(cells):
        bend = i > 0 and (cells[i - 1][2], cells[i - 1][3]) != (dx, dy)
        g.put(x, y, VEC2ARROW[(dx, dy)] if (i == 0 or i == len(cells) - 1 or bend) else
              ('-' if dx else '|'))
    return len(cells)


class RGrid:
    """Grid-compatible shim over tools/router.Router, so the room builders below can
    stamp into the global rip-up router's typed occupancy grid unchanged."""

    class _Cells(dict):
        """prog.cells view that also clears the router's TYPE on delete -- otherwise a
        temporary reservation leaves the cell permanently non-FREE."""

        def __init__(self, grid, typ):
            super().__init__()
            self.grid, self.typ = grid, typ

        def __delitem__(self, k):
            self.grid.pop(k, None)
            self.typ.pop(k, None)

        def pop(self, k, default=None):
            self.typ.pop(k, None)
            return self.grid.pop(k, default)

        def __contains__(self, k):
            return k in self.grid

        def __getitem__(self, k):
            return self.grid[k]

        def items(self):
            return self.grid.items()

    def __init__(self, router):
        import router as _r
        self.R = router
        self.T = _r
        self.c = RGrid._Cells(router.grid.prog.cells, router.grid.typ)

    def put(self, x, y, ch, force=False):
        cur = self.R.grid.glyph(x, y)
        if not force and cur != ' ' and cur != ch:
            raise ValueError(f"collision at ({x},{y}): {cur!r} vs {ch!r}")
        self.R.grid.set(x, y, self.T.PLACED, ch)

    def put_pipe(self, x, y, ch):
        self.R.grid.set(x, y, self.T.PIPE, ch)

    def get(self, x, y):
        # a ROOM interior is blank but must never be routed through
        if self.R.grid.t(x, y) != self.T.FREE:
            return self.R.grid.glyph(x, y) if self.R.grid.glyph(x, y) != ' ' else '#'
        return self.R.grid.glyph(x, y)

    def text(self, x, y, s, d="E"):
        dx, dy = DIRS[d]
        for i, ch in enumerate(s):
            if ch != '\0':
                self.put(x + i * dx, y + i * dy, ch)

    def room(self, x, y, w, h):
        self.R.add_room(x, y, w, h)
        return Room(x, y, w, h)

    def render(self):
        return self.R.grid.prog.render()

    def footprint(self):
        return self.R.grid.prog.footprint()
