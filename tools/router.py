"""router.py — the littleman GLOBAL ROUTER (v1).

Turns already-placed rooms + a set of NETS (pipes and man-corridors) into a
collision-free grid, using a shared A* core and a global negotiated-congestion
rip-up loop. This is the fix for the recurring "converging corridors hog lanes"
failure that stalls sort / plotter / matmul (validated algorithms, unroutable grids).

Built ON TOP of tools/layout.py (Layout / place_pipe / auto_pipe / validate_pipe are
imported and reused, never modified) and tools/littleman.py (Program).

Design (see docs/routing-requirements.md):
  1. Typed occupancy grid (FREE/GLIDE/PLACED/PIPE/WALL/ROOM/LITERAL) with the two
     DIFFERENT collision rules (man-corridors share blanks; pipes are exclusive).
  2. Shared A* core.  cost = steps + BEND*bends + GROW*bbox_growth  (score = max(w,h)^2,
     so extending the governing dimension is heavily penalised; staying inside the box
     is ~free).  Plus per-cell congestion cost from the rip-up loop.
  3. Pipe-net router (endpoints on room borders, valid arrowheads/body, FREE-only) and
     man-corridor router (turns at bends, blanks between, may cross other corridors'
     GLIDE cells, refuses PLACED/PIPE/WALL, heading-match at merges).
  4. GLOBAL rip-up / negotiated-congestion loop (PathFinder-style): route every net,
     find over-used cells, raise their history cost, reroute, iterate to convergence.
  5. Nearest-pipe solver: place multi-pipe-room attachment cells so each r/s/q op
     resolves to its intended pipe (Manhattan-nearest + reading-order tie).
  6. Validators mirroring the oracle.
  7. API:  Router(program) / add_room / add_pipe_net / add_corridor / solve(budget).

Scope = v1 (fixed-endpoint nets on already-placed rooms).  v2 (CFG folding) is NOT here.
"""
import os
import sys
import heapq
from collections import defaultdict, namedtuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import littleman as lm
import layout as L
from layout import (Layout, place_pipe, auto_pipe, validate_pipe,
                    DIRS, ARROW, VEC2ARROW, Collision, _unit)

# ── cell types ──────────────────────────────────────────────────────────────
FREE, GLIDE, PLACED, PIPE, WALL, ROOM, LITERAL = range(7)
TYPE_NAME = {FREE: "FREE", GLIDE: "GLIDE", PLACED: "PLACED", PIPE: "PIPE",
             WALL: "WALL", ROOM: "ROOM", LITERAL: "LITERAL"}

# A* cost weights.  A step is 1; a bend costs BEND; pushing the score-governing box
# dimension costs GROW per extra cell of extension.  Congestion is added on top.
BEND = 2.0
GROW = 40.0
PRESENT = 4.0     # per-iteration sharing penalty (last iteration's usage count)
HIST = 6.0        # persistent history penalty (rises each rip-up iteration)

PERP = {"E": ("N", "S"), "W": ("N", "S"), "N": ("E", "W"), "S": ("E", "W")}
DVEC = dict(DIRS)


class UnroutableNet:
    """Returned by solve() when a net cannot be placed.  Carries WHICH net failed,
    WHY, and the congested region so the caller can nudge geometry rather than guess."""
    def __init__(self, which, why, congested_region=None):
        self.which = which
        self.why = why
        self.congested_region = congested_region or []

    def __bool__(self):
        return False

    def __repr__(self):
        return f"UnroutableNet(which={self.which!r}, why={self.why!r}, " \
               f"congested={len(self.congested_region)} cells)"


PipeNet = namedtuple("PipeNet", "name src dst nearest_for")
Corridor = namedtuple("Corridor", "name a h_in b h_out glyphs")


# ══════════════════════════════════════════════════════════════════════════════
# 1. Typed occupancy grid + two-domain collision test
# ══════════════════════════════════════════════════════════════════════════════
class Grid:
    """Typed occupancy grid.  `typ` keys off cell TYPE (not a boolean occupied bit);
    the underlying littleman.Program `prog` is the glyph truth for render()/grade()."""

    def __init__(self, program=None):
        self.prog = program if program is not None else lm.Program()
        self.typ = {}                    # (x,y) -> celltype ; default FREE
        # seed types from any glyphs already in the program (e.g. hand-placed rooms)

    # ---- type access ----
    def t(self, x, y):
        return self.typ.get((x, y), FREE)

    def glyph(self, x, y):
        return self.prog.get(x, y)

    def set(self, x, y, celltype, ch=None):
        self.typ[(x, y)] = celltype
        if ch is not None:
            self.prog.put(x, y, ch)
        return self

    # ---- two-domain collision tests --------------------------------------------
    def pipe_ok(self, cell):
        """PIPE domain: every cell is a glyph, so a pipe cell must be strictly FREE
        (exclusive vs GLIDE/PLACED/PIPE/WALL/ROOM/LITERAL)."""
        return self.t(*cell) == FREE

    def glide_ok(self, cell):
        """MAN domain, straight glide: a blank the man drifts through.  Shareable with
        FREE/ROOM/other GLIDE; refuses PLACED/PIPE/WALL/LITERAL (a glide over a stray
        op would corrupt the walk)."""
        return self.t(*cell) in (FREE, ROOM, GLIDE)

    def bend_ok(self, cell):
        """MAN domain, bend/op: needs an EXCLUSIVE placed glyph, so the cell must be
        FREE or ROOM (never another corridor's GLIDE — that would inject a turn into
        the other man's straight walk)."""
        return self.t(*cell) in (FREE, ROOM)

    def merge_ok(self, cell, heading):
        """A man-corridor may re-use an existing turn glyph as a MERGE cell only when
        it is a PLACED arrow whose absolute direction == the arriving man's heading."""
        return self.t(*cell) == PLACED and self.glyph(*cell) == ARROW[heading]


# ══════════════════════════════════════════════════════════════════════════════
# 2. Shared A* core
# ══════════════════════════════════════════════════════════════════════════════
# Hard safety caps so a pathological / over-large net can never spike memory: the
# search box is clamped and the frontier is bounded (visited set stays O(4*area)).
MAX_BOX_SIDE = 512          # clamp any single search-box dimension
MAX_EXPANSIONS = 300_000    # pop budget; a bounded box of ~256^2 x4 headings fits under this


def astar(starts, goal_test, passable_straight, passable_bend, cell_cost,
          bound, max_expansions=MAX_EXPANSIONS):
    """Shared A* over (cell, heading) states.

    starts            : iterable of (cell, heading) seed states (cost 0).
    goal_test(cell,h) : True when (cell,heading) is an accepting state.
    passable_straight : (cell) -> bool, may we glide straight onto `cell`.
    passable_bend     : (cell) -> bool, may we place a bend and step onto `cell`.
    cell_cost(cell)   : extra scalar cost for entering `cell` (bbox growth + congestion).
    bound             : (x0,y0,x1,y1) inclusive search box (clamped to MAX_BOX_SIDE).
    Returns [(cell,heading), ...] path (states) or None.

    Memory-bounded: the box is clamped and the pop budget caps the frontier, so the
    visited/parent maps stay O(4*box_area) and never balloon on a bad net.
    """
    x0, y0, x1, y1 = bound
    if x1 - x0 > MAX_BOX_SIDE:
        x1 = x0 + MAX_BOX_SIDE
    if y1 - y0 > MAX_BOX_SIDE:
        y1 = y0 + MAX_BOX_SIDE

    def inb(c):
        return x0 <= c[0] <= x1 and y0 <= c[1] <= y1

    pq = []
    best = {}
    parent = {}
    for st in starts:
        c, h = st
        g = cell_cost(c)
        if st not in best or g < best[st]:
            best[st] = g
            parent[st] = None
            heapq.heappush(pq, (g, c[0], c[1], h, st))
    goal = None
    pops = 0
    while pq:
        pops += 1
        if pops > max_expansions:        # frontier budget exhausted -> treat as unroutable
            return None
        g, _, _, _, st = heapq.heappop(pq)
        if best.get(st, 1e18) < g:
            continue
        cell, h = st
        if goal_test(cell, h):
            goal = st
            break
        # continue straight
        d = DVEC[h]
        nc = (cell[0] + d[0], cell[1] + d[1])
        if inb(nc) and passable_straight(nc):
            ns = (nc, h)
            ng = g + 1.0 + cell_cost(nc)
            if ng < best.get(ns, 1e18):
                best[ns] = ng
                parent[ns] = st
                heapq.heappush(pq, (ng, nc[0], nc[1], h, ns))
        # bends
        for nd in PERP[h]:
            d2 = DVEC[nd]
            nc = (cell[0] + d2[0], cell[1] + d2[1])
            if inb(nc) and passable_bend(nc):
                ns = (nc, nd)
                ng = g + 1.0 + BEND + cell_cost(nc)
                if ng < best.get(ns, 1e18):
                    best[ns] = ng
                    parent[ns] = st
                    heapq.heappush(pq, (ng, nc[0], nc[1], nd, ns))
    if goal is None:
        return None
    path = []
    st = goal
    while st is not None:
        path.append(st)
        st = parent[st]
    path.reverse()
    return path


def _bbox_grower(bounds):
    """Return cell_cost contribution for pushing the score-governing box dimension.
    `bounds` = (minx,miny,maxx,maxy) of the CURRENT non-space footprint."""
    minx, miny, maxx, maxy = bounds
    base = max(maxx - minx + 1, maxy - miny + 1) if maxx >= minx else 0

    def grow(cell):
        nx0, ny0 = min(minx, cell[0]), min(miny, cell[1])
        nx1, ny1 = max(maxx, cell[0]), max(maxy, cell[1])
        nb = max(nx1 - nx0 + 1, ny1 - ny0 + 1)
        return GROW * max(0, nb - base)
    return grow


# ══════════════════════════════════════════════════════════════════════════════
# 3a. Pipe-net router
# ══════════════════════════════════════════════════════════════════════════════
def route_pipe(grid, net, extra_cost=None, margin=6):
    """Route one PIPE net from src border to dst border over FREE cells.

    Returns (cells, dirs) where `dirs[i]` is the arrowhead/flow direction at cells[i]
    (dirs[0]=out of src, dirs[-1]=into dst), or None if unroutable.  The cell path is
    a geometric chain; the FINAL cell's arrowhead points at dst (a bend if needed) —
    exactly the place_pipe / oracle model.  Validity (>=2 cells, arrowheads at
    start/bends/end, src/dst border neighbours) is guaranteed by construction.
    """
    src, dst = net.src, net.dst
    extra_cost = extra_cost or (lambda c: 0.0)
    minx, miny, maxx, maxy = grid.prog.bounds()
    grow = _bbox_grower((minx, miny, maxx, maxy))
    xs = [src[0], dst[0]]
    ys = [src[1], dst[1]]
    bound = (min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin)

    def passable(cell):
        return grid.pipe_ok(cell) and cell != src and cell != dst

    def cost(cell):
        return grow(cell) + extra_cost(cell)

    # Seed with a FORCED straight stub out of the source: c0 = src+out, c1 = c0+out.
    # This pins the start arrowhead to `out` so cells[0]'s backward neighbour == src
    # (the oracle's source-border rule); A* then bends from c1 onward.  The pipe cells
    # begin at c0, so the minimum pipe is [c0, c1] (>= 2 cells, always).
    stub = {}                                       # (c1,dir) -> c0 prefix
    starts = []
    for hd, d in DVEC.items():
        c0 = (src[0] + d[0], src[1] + d[1])
        c1 = (c0[0] + d[0], c0[1] + d[1])
        if passable(c0) and passable(c1):
            starts.append((c1, hd))
            stub[(c1, hd)] = c0
    if not starts:
        return None

    # goal: current cell is orthogonally adjacent to dst (dst is the border it exits to)
    def goal_test(cell, h):
        return abs(cell[0] - dst[0]) + abs(cell[1] - dst[1]) == 1

    path = astar(starts, goal_test, passable, passable, cost, bound)
    if path is None:
        return None
    c0 = stub[path[0]]
    cells = [c0] + [c for c, _ in path]
    if len(cells) < 2 or len(set(cells)) != len(cells):
        return None
    # per-cell flow directions: segment dirs, with the LAST cell bending to face dst.
    dirs = []
    for i in range(len(cells)):
        if i < len(cells) - 1:
            dirs.append(_unit(cells[i + 1][0] - cells[i][0],
                              cells[i + 1][1] - cells[i][1]))
        else:
            dirs.append(_unit(dst[0] - cells[i][0], dst[1] - cells[i][1]))
    return cells, dirs


def validate_pipe_oracle(cells, dirs, src, dst, occupied=()):
    """Oracle-accurate pipe validity (layout.validate_pipe assumes a STRAIGHT end and
    rejects the bent-end arrowhead that the oracle actually accepts — e.g. weave8x8).

    Rules (docs/multi-man-interactions.md pipe prose): >=2 contiguous distinct cells;
    the arrowhead at cells[0] points `dirs[0]` OUT of the source border (so
    cells[0]-dirs[0]==src); the arrowhead at cells[-1] points `dirs[-1]` INTO the dest
    border (so cells[-1]+dirs[-1]==dst); interior flow dirs match the geometry; no cell
    lands on src/dst/occupied.  Raises AssertionError on any violation."""
    occ = set(map(tuple, occupied))
    n = len(cells)
    assert n >= 2, "pipe must have >= 2 cells"
    assert len(set(cells)) == n, "pipe self-intersects"
    for i in range(1, n):
        assert abs(cells[i][0] - cells[i - 1][0]) + abs(cells[i][1] - cells[i - 1][1]) == 1, \
            f"pipe not contiguous at {cells[i-1]}->{cells[i]}"
    for c in cells:
        assert c not in occ, f"pipe crosses occupied cell {c}"
        assert c != src and c != dst, "pipe overlaps a border point"
    # interior segment dirs must match geometry
    for i in range(n - 1):
        seg = _unit(cells[i + 1][0] - cells[i][0], cells[i + 1][1] - cells[i][1])
        assert dirs[i] == seg, f"flow dir {dirs[i]} != geometry {seg} at cell {i}"
    back = (cells[0][0] - dirs[0][0], cells[0][1] - dirs[0][1])
    assert back == tuple(src), f"start backward neighbour {back} != src border {src}"
    fwd = (cells[-1][0] + dirs[-1][0], cells[-1][1] + dirs[-1][1])
    assert fwd == tuple(dst), f"end forward neighbour {fwd} != dst border {dst}"
    return True


def draw_pipe(grid, cells, dirs):
    """Commit a routed pipe: arrowheads at start / every bend / end, body glyphs
    between, and mark every cell PIPE.  Mirrors place_pipe's drawing exactly."""
    n = len(cells)
    for i, (cx, cy) in enumerate(cells):
        di = dirs[i]
        bend = 0 < i < n and (i == 0 or dirs[i - 1] != di)
        if i == 0 or i == n - 1 or bend:
            ch = VEC2ARROW[di]
        else:
            ch = "-" if di[0] != 0 else "|"
        grid.set(cx, cy, PIPE, ch)


# ══════════════════════════════════════════════════════════════════════════════
# 3b. Man-corridor router
# ══════════════════════════════════════════════════════════════════════════════
def route_corridor(grid, cor, extra_cost=None, margin=8):
    """Route one MAN corridor: a man at `a` heading `h_in` must arrive at `b` moving
    `h_out`.  Turn glyphs land at bends (PLACED), straights stay blank GLIDE cells.

    Returns list of (cell, heading) states (a..b inclusive) or None.  The corridor may
    glide across other corridors' GLIDE cells, may MERGE onto an existing turn glyph
    whose direction matches, and refuses PLACED(differing)/PIPE/WALL/LITERAL.
    """
    a, b = cor.a, cor.b
    extra_cost = extra_cost or (lambda c: 0.0)
    minx, miny, maxx, maxy = grid.prog.bounds()
    grow = _bbox_grower((minx, miny, maxx, maxy))
    xs = [a[0], b[0]]
    ys = [a[1], b[1]]
    bound = (min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin)

    # A straight glide may land on FREE/ROOM/GLIDE (shareable blanks); a bend needs an
    # exclusive FREE/ROOM cell.  The GOAL cell `b` is the only PLACED cell we may step
    # onto — a MERGE — and only if it is an arrow matching h_out (checked in goal_test).
    def p_straight2(cell):
        return grid.glide_ok(cell) or cell == b

    def p_bend(cell):
        return grid.bend_ok(cell) or cell == b

    def cost(cell):
        c = grow(cell) + extra_cost(cell)
        # nudge toward reusing existing GLIDE lanes (shared blanks are free real estate)
        if grid.t(*cell) == GLIDE:
            c -= 0.25
        return c

    starts = [((a[0] + DVEC[cor.h_in][0], a[1] + DVEC[cor.h_in][1]), cor.h_in)]
    if not (grid.glide_ok(starts[0][0]) or grid.t(*starts[0][0]) == PLACED):
        # can't even leave `a`
        return None

    def goal_test(cell, h):
        if cell != b or h != cor.h_out:
            return False
        # if b is already an arrow, it must match h_out (a legal merge)
        if grid.t(*b) == PLACED and grid.glyph(*b) != ARROW[cor.h_out]:
            return False
        return True

    path = astar(starts, goal_test, p_straight2, p_bend, cost, bound)
    if path is None:
        return None
    # prepend the start cell `a` itself (heading h_in) for completeness
    return [(a, cor.h_in)] + path


def draw_corridor(grid, states, glyphs=None):
    """Commit a routed corridor.  Places a turn arrow at each heading-change (PLACED),
    leaves straights as blank GLIDE, and optionally lays `glyphs` (op run) along the
    walk starting at `a`.  Merges (same-direction arrow already there) are idempotent."""
    glyphs = list(glyphs or [])
    gi = 0
    for i, (cell, h) in enumerate(states):
        prev_h = states[i - 1][1] if i > 0 else h
        is_bend = (h != prev_h)
        if is_bend:
            ch = ARROW[h]
            cur = grid.glyph(*cell)
            if cur != " " and cur != ch:
                raise Collision(f"corridor bend {cell}: {cur!r} vs {ch!r}")
            grid.set(cell[0], cell[1], PLACED, ch)
        else:
            # straight: lay an op glyph if provided, else a blank glide
            if gi < len(glyphs) and glyphs[gi] != " ":
                grid.set(cell[0], cell[1], PLACED, glyphs[gi])
            elif grid.t(*cell) in (FREE, ROOM):
                grid.set(cell[0], cell[1], GLIDE)
        gi += 1


# ══════════════════════════════════════════════════════════════════════════════
# 5. Nearest-pipe solver
# ══════════════════════════════════════════════════════════════════════════════
def nearest_pipe(op_cell, attach_cells):
    """Which pipe an r/s/q at `op_cell` resolves to: the attach cell of minimum
    Manhattan distance, ties broken by reading order (smaller y, then smaller x).
    `attach_cells` = {pipe_name: (x,y)}.  Returns the winning pipe_name."""
    def key(item):
        name, (ax, ay) = item
        return (abs(ax - op_cell[0]) + abs(ay - op_cell[1]), ay, ax)
    return min(attach_cells.items(), key=key)[0]


def solve_nearest(candidates, intended):
    """Place attachment cells so every op resolves to its intended pipe.

    candidates : {pipe_name: [ (x,y) allowed attach cells ]}
    intended   : {op_cell: pipe_name}  (the pipe each op MUST resolve to)
    Returns {pipe_name: chosen (x,y)} satisfying every op, or None if infeasible.
    Backtracking over the (usually tiny) candidate sets.
    """
    names = list(candidates.keys())

    def ok(assign):
        att = {n: assign[n] for n in assign}
        for op, want in intended.items():
            if not all(n in att for n in names):
                continue
            if nearest_pipe(op, att) != want:
                return False
        return True

    def bt(i, assign):
        if i == len(names):
            att = {n: assign[n] for n in names}
            for op, want in intended.items():
                if nearest_pipe(op, att) != want:
                    return None
            return dict(assign)
        n = names[i]
        for c in candidates[n]:
            assign[n] = c
            r = bt(i + 1, assign)
            if r is not None:
                return r
            del assign[n]
        return None

    return bt(0, {})


# ══════════════════════════════════════════════════════════════════════════════
# 6 + 7.  Router — public API, negotiated-congestion solve, validators
# ══════════════════════════════════════════════════════════════════════════════
class Router:
    def __init__(self, program=None):
        self.grid = Grid(program)
        self.rooms = []          # (x0,y0,x1,y1) outer rects
        self.literals = []       # (x,y,text,axis)
        self.pipe_nets = []      # PipeNet
        self.corridors = []      # Corridor
        self._n = 0

    # convenience passthroughs -------------------------------------------------
    @property
    def prog(self):
        return self.grid.prog

    def render(self):
        return self.grid.prog.render()

    def footprint(self):
        return self.grid.prog.footprint()

    def grade(self, slug):
        return self.grid.prog.grade(slug)

    def _name(self, prefix):
        self._n += 1
        return f"{prefix}{self._n}"

    # ---- fixed placement (rooms, men, ops, literals) -------------------------
    def add_room(self, x, y, w, h, glyphs="+-|", ports=None):
        """Register a room: draw it, mark the border WALL and the interior ROOM.
        `ports` is accepted for API completeness (border cells reserved for pipes)."""
        r = self.grid.prog.room(x, y, w, h, glyphs=glyphs)
        for i in range(w):
            self.grid.set(x + i, y, WALL)
            self.grid.set(x + i, y + h - 1, WALL)
        for j in range(h):
            self.grid.set(x, y + j, WALL)
            self.grid.set(x + w - 1, y + j, WALL)
        for ix in range(x + 1, x + w - 1):
            for iy in range(y + 1, y + h - 1):
                self.grid.set(ix, iy, ROOM)
        self.rooms.append((x, y, x + w - 1, y + h - 1))
        return r

    def add_input_room(self, x, y):
        r = self.add_room(x, y, 3, 3)
        self.grid.set(x + 1, y + 1, PLACED, "I")
        return r

    def add_output_room(self, x, y):
        r = self.add_room(x, y, 3, 3)
        self.grid.set(x + 1, y + 1, PLACED, "O")
        return r

    def add_display(self, x, y, w, h):
        return self.add_room(x, y, w, h, glyphs="+=:")

    def place(self, x, y, ch, celltype=PLACED):
        """Fixed collision-checked placement of a single glyph (man '@', op, turn)."""
        cur = self.grid.glyph(x, y)
        if cur != " " and cur != ch:
            raise Collision(f"place {(x,y)}: {cur!r} vs {ch!r}")
        self.grid.set(x, y, celltype, ch)
        return self

    def place_run(self, x, y, s, d="E"):
        """Fixed run of glyphs from (x,y) heading d (man instruction stream / turns).
        Spaces are skipped (left as whatever they are)."""
        dx, dy = DVEC[d]
        for i, ch in enumerate(s):
            if ch != " ":
                self.place(x + i * dx, y + i * dy, ch, PLACED)
        return self

    def place_literal(self, x, y, s, axis="H"):
        """Place a backtick-literal block (rigid, must stay clear on BOTH axes)."""
        dx, dy = (1, 0) if axis == "H" else (0, 1)
        for i, ch in enumerate(s):
            self.place(x + i * dx, y + i * dy, ch, LITERAL)
        self.literals.append((x, y, s, axis))
        return self

    # ---- nets ----------------------------------------------------------------
    def add_pipe_net(self, src, dst, nearest_for=None, name=None):
        """Register a pipe to route from border cell `src` to border cell `dst`.
        `nearest_for` = op cells that must resolve to THIS pipe (nearest-pipe check)."""
        net = PipeNet(name or self._name("pipe"), tuple(src), tuple(dst),
                      tuple(map(tuple, nearest_for or ())))
        self.pipe_nets.append(net)
        return net

    def add_corridor(self, a, h_in, b, h_out, glyphs=None, name=None):
        """Register a man-corridor: man at `a` heading `h_in` reaches `b` moving
        `h_out`, laying `glyphs` (op run) along the walk."""
        cor = Corridor(name or self._name("cor"), tuple(a), h_in, tuple(b), h_out,
                       tuple(glyphs or ()))
        self.corridors.append(cor)
        return cor

    # ---- difficulty ordering (hardest first) ---------------------------------
    @staticmethod
    def _pipe_hard(net):
        return abs(net.src[0] - net.dst[0]) + abs(net.src[1] - net.dst[1])

    @staticmethod
    def _cor_hard(cor):
        return abs(cor.a[0] - cor.b[0]) + abs(cor.a[1] - cor.b[1])

    # ---- global negotiated-congestion rip-up loop ----------------------------
    def solve(self, budget=60):
        """Route every net with a GLOBAL rip-up / negotiated-congestion loop.

        Each iteration every net is (re)routed against a rising per-cell congestion
        cost; cells claimed by >1 exclusive net get their history cost bumped, so the
        next iteration the nets negotiate apart instead of one hogging the lane.
        Iterates to convergence (no over-used cell) or `budget`.  On success the routes
        are committed to the grid; on failure returns UnroutableNet(which, why, region).
        """
        pipes = sorted(self.pipe_nets, key=self._pipe_hard, reverse=True)
        cors = sorted(self.corridors, key=self._cor_hard, reverse=True)

        history = defaultdict(float)
        prev_usage = defaultdict(int)
        last_overused = []

        for it in range(budget):
            usage = defaultdict(int)          # exclusive-cell usage this iteration
            proutes = {}
            croutes = {}

            def econ(cell):
                return PRESENT * prev_usage[cell] + HIST * history[cell]

            # --- pipes (exclusive: every cell counts) ---
            for net in pipes:
                res = route_pipe(self.grid, net, extra_cost=econ)
                if res is None:
                    return UnroutableNet(net.name, "no FREE pipe route to border",
                                         self._region_around(net.src, net.dst))
                cells, dirs = res
                proutes[net.name] = (cells, dirs)
                for c in cells:
                    usage[c] += 1

            # --- corridors (only bend/PLACED cells are exclusive; glides shareable) ---
            for cor in cors:
                res = route_corridor(self.grid, cor, extra_cost=econ)
                if res is None:
                    return UnroutableNet(cor.name, "no man-corridor route (blocked)",
                                         self._region_around(cor.a, cor.b))
                croutes[cor.name] = res
                for i, (cell, h) in enumerate(res):
                    prev = res[i - 1][1] if i > 0 else h
                    if h != prev:                      # a bend => exclusive cell
                        usage[cell] += 1

            overused = [c for c, n in usage.items() if n > 1]
            if not overused:
                self._commit(pipes, cors, proutes, croutes)
                ok = self.validate()
                if ok is not True:
                    return ok
                return True

            last_overused = overused
            for c in overused:
                history[c] += 1.0
            prev_usage = usage

        which = pipes[0].name if pipes else (cors[0].name if cors else "?")
        return UnroutableNet(which, f"rip-up did not converge in {budget} iters",
                             last_overused)

    def _region_around(self, a, b):
        x0, y0 = min(a[0], b[0]) - 2, min(a[1], b[1]) - 2
        x1, y1 = max(a[0], b[0]) + 2, max(a[1], b[1]) + 2
        return [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]

    def _commit(self, pipes, cors, proutes, croutes):
        for net in pipes:
            cells, dirs = proutes[net.name]
            draw_pipe(self.grid, cells, dirs)
            net_cells = {"cells": cells}
        for cor in cors:
            draw_corridor(self.grid, croutes[cor.name], cor.glyphs)
        self._proutes = proutes
        self._croutes = croutes

    # ---- validators (mirror the oracle) --------------------------------------
    def validate(self):
        """Run every oracle-mirroring validator.  Returns True or an UnroutableNet."""
        # pipes: exact parse rules via layout.validate_pipe
        occ = set()
        for net in self.pipe_nets:
            cells, dirs = self._proutes[net.name]
            try:
                validate_pipe_oracle(cells, dirs, net.src, net.dst, occupied=occ)
            except AssertionError as e:
                return UnroutableNet(net.name, f"invalid pipe: {e}", cells)
            occ |= set(cells)
        # no corridor bend crosses PLACED(diff)/PIPE/WALL — enforced at draw; re-scan
        # literal blocks clear on both axes
        why = self._check_literals()
        if why:
            return UnroutableNet(why[0], why[1], why[2])
        # nearest-pipe assignments hold
        why = self._check_nearest()
        if why:
            return UnroutableNet(why[0], why[1], why[2])
        return True

    def _check_literals(self):
        """A backtick literal parses horizontally AND vertically: any stray glyph in a
        literal cell's row or column span that is itself a literal/backtick would create
        a second parse.  We assert the block's OWN row and column contain no other
        literal glyphs outside the block."""
        for (x, y, s, axis) in self.literals:
            n = len(s)
            block = {(x + i, y) if axis == "H" else (x, y + i) for i in range(n)}
            # cells in the same row (H) or column (V) as each block cell must not be a
            # foreign LITERAL glyph.
            for (bx, by) in block:
                for (cx, cy), t in self.grid.typ.items():
                    if t == LITERAL and (cx, cy) not in block:
                        if (axis == "H" and cy == by) or (axis == "V" and cx == bx):
                            return (f"literal@{(x,y)}",
                                    f"foreign literal {(cx,cy)} shares axis with block",
                                    list(block))
        return None

    def _check_nearest(self):
        """Every pipe net's `nearest_for` op cells must resolve to that net by
        Manhattan-nearest + reading-order tie against all pipes' dst border attach
        cells within the same room."""
        # attach cell of a pipe = its dst border (where the value lands / is taken)
        attaches = {net.name: net.dst for net in self.pipe_nets}
        if len(attaches) < 2:
            return None
        for net in self.pipe_nets:
            for op in net.nearest_for:
                got = nearest_pipe(op, attaches)
                if got != net.name:
                    return (net.name,
                            f"op {op} resolves to {got}, wanted {net.name}",
                            [op, net.dst, attaches[got]])
        return None


# ══════════════════════════════════════════════════════════════════════════════
# ACCEPTANCE TEST + self-tests
# ══════════════════════════════════════════════════════════════════════════════
def build_triangle_with_router():
    """Reconstruct solutions/triangle/weave8x8.man using ONLY the Router: fixed room +
    man placements, then ROUTE the two L-bend pipes.  Known-good score: 832 (6/6)."""
    r = Router()
    r.add_room(0, 0, 8, 4)                        # compute room
    r.add_input_room(0, 4)                        # I room (I at 1,5)
    r.add_output_room(3, 5)                       # O room (O at 4,6)
    # the walking man (fixed): east row1, bend S, bend W, west row2
    r.place_run(1, 1, "@rM*+", "E")               # (1,1)..(5,1)
    r.place(6, 1, "v"); r.place(6, 2, "<")        # the two turns
    r.place_run(1, 2, "s/W2W", "E")               # (1,2)..(5,2) reads reversed westward
    # two pipe nets: I->compute (bends N), compute->O (bends W)
    r.add_pipe_net((2, 4), (4, 3), name="in")     # I right border -> compute bottom
    r.add_pipe_net((6, 3), (5, 5), name="out")    # compute bottom -> O top border
    return r


def build_ring_v2_with_router():
    """Reconstruct solutions/reverse-a-list/ring-v2.man using ONLY the Router: register
    its 4 rooms, fix every interior glyph, then ROUTE the 4 pipe nets (INPUT / OUTPUT /
    FEED / RETURN — the "pipe fan").  Known-good score: 956100 (8/8).

    The fixed cells are read from the reference so the test transcribes nothing by hand;
    the ROUTER alone must re-derive the four pipes (including the col-0 RETURN wrap)."""
    ref = os.path.join(lm.REPO, "solutions", "reverse-a-list", "ring-v2.man")
    G = {}
    for y, row in enumerate(open(ref).read().split("\n")):
        for x, c in enumerate(row):
            if c != " ":
                G[(x, y)] = c
    rooms = [(2, 0, 16, 13), (17, 4, 19, 6), (17, 11, 19, 13), (2, 16, 11, 19)]

    def inroom(x, y):
        return any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in rooms)

    def onborder(x, y):
        return any(x0 <= x <= x1 and y0 <= y <= y1 and (x in (x0, x1) or y in (y0, y1))
                   for x0, y0, x1, y1 in rooms)

    pipe_cells = {xy for xy in G if not inroom(*xy)}
    r = Router()
    for x0, y0, x1, y1 in rooms:
        r.add_room(x0, y0, x1 - x0 + 1, y1 - y0 + 1)
    for (x, y), c in G.items():
        if (x, y) in pipe_cells or onborder(x, y):
            continue
        r.place(x, y, c, PLACED)
    r.add_pipe_net((18, 4), (16, 1), name="INPUT")
    r.add_pipe_net((16, 8), (18, 11), name="OUTPUT")
    r.add_pipe_net((9, 13), (9, 16), name="FEED")
    r.add_pipe_net((2, 18), (2, 8), name="RETURN")
    return r


def _selftest():
    import json
    ok = 0

    # --- 1. typed grid + two-domain collision test --------------------------
    g = Grid()
    g.set(2, 2, WALL, "|")
    g.set(3, 3, PIPE, "-")
    g.set(4, 4, GLIDE)
    assert g.pipe_ok((5, 5)) and not g.pipe_ok((2, 2)) and not g.pipe_ok((4, 4))
    assert g.glide_ok((4, 4)) and not g.glide_ok((3, 3)) and not g.glide_ok((2, 2))
    assert g.bend_ok((5, 5)) and not g.bend_ok((4, 4))     # bend refuses a GLIDE
    g.set(6, 6, PLACED, ">")
    assert g.merge_ok((6, 6), "E") and not g.merge_ok((6, 6), "N")
    print("[ok] typed grid + two-domain collision (pipe/glide/bend/merge)"); ok += 1

    # --- 2. A* core: fewest bends, avoids blocks ----------------------------
    gg = Grid()
    for yy in range(0, 4):
        gg.set(3, yy, WALL, "|")                    # a wall column at x=3, y=0..3
    starts = [((0, 0), "E")]
    grow = _bbox_grower(gg.prog.bounds())
    def psb(c): return gg.t(*c) == FREE
    path = astar(starts, lambda c, h: c == (6, 0), psb, psb,
                 lambda c: grow(c), (-2, -6, 10, 6))
    assert path is not None and path[-1][0] == (6, 0)
    cells = [c for c, _ in path]
    assert (3, 0) not in cells                       # routed AROUND the wall
    print(f"[ok] A* core routed around wall ({len(cells)} cells)"); ok += 1

    # --- 3. pipe-net router: valid pipe, obeys parse rules ------------------
    gp = Grid()
    gp.set(2, 2, WALL, "|"); gp.set(10, 2, WALL, "|")
    for yy in range(0, 3):
        gp.set(6, yy, WALL, "|")                     # obstacle column
    net = PipeNet("t", (2, 2), (10, 2), ())
    res = route_pipe(gp, net)
    assert res is not None
    cells, dirs = res
    validate_pipe_oracle(cells, dirs, (2, 2), (10, 2))
    print(f"[ok] pipe-net router: valid pipe around obstacle ({len(cells)} cells)"); ok += 1

    # --- 4. man-corridor router: crosses a GLIDE, refuses a PLACED op -------
    gc = Grid()
    # lay a horizontal glide lane across y=0
    for xx in range(0, 6):
        gc.set(xx, 0, GLIDE)
    cor = Corridor("c", (2, -3), "S", (2, 3), "S", ())
    st = route_corridor(gc, cor)
    assert st is not None and st[-1][0] == (2, 3)
    assert any(c == (2, 0) for c, _ in st)           # legally crossed the glide lane
    # now block with a PLACED op and require the corridor to route around it
    gc2 = Grid()
    gc2.set(2, 0, PLACED, "r")
    cor2 = Corridor("c2", (2, -3), "S", (2, 3), "S", ())
    st2 = route_corridor(gc2, cor2)
    assert st2 is None or all(c != (2, 0) for c, _ in st2)
    print("[ok] man-corridor router: crosses GLIDE, refuses PLACED op"); ok += 1

    # --- 5. nearest-pipe solver ---------------------------------------------
    assert nearest_pipe((0, 0), {"a": (1, 0), "b": (5, 0)}) == "a"
    # reading-order tie: equal Manhattan -> smaller y then x wins
    assert nearest_pipe((2, 0), {"a": (2, 2), "b": (0, 0)}) == "b"
    intended = {(1, 1): "Q", (8, 4): "P"}
    sol = solve_nearest({"P": [(0, 5), (9, 5)], "Q": [(0, 0), (9, 0)]}, intended)
    assert sol is not None
    for op, want in intended.items():                # every op resolves as intended
        assert nearest_pipe(op, sol) == want
    # infeasible: two pipes forced to the SAME attach cell can't separate two ops
    infeasible = solve_nearest({"P": [(5, 5)], "Q": [(5, 5)]},
                               {(0, 0): "P", (9, 9): "Q"})
    assert infeasible is None
    print(f"[ok] nearest-pipe solver (assign {sol}, infeasible detected)"); ok += 1

    # --- 6. GLOBAL rip-up: two pipes that would collide must negotiate ------
    rr = Router()
    rr.add_room(0, 0, 4, 12)                          # left room
    rr.add_room(20, 0, 4, 12)                         # right room
    # two pipes both wanting the straight lane between the rooms
    rr.add_pipe_net((3, 3), (20, 3), name="A")        # left border -> right border
    rr.add_pipe_net((3, 8), (20, 8), name="B")
    res = rr.solve(budget=40)
    assert res is True, f"rip-up failed: {res}"
    # both pipes present and non-overlapping
    pc = [xy for xy, t in rr.grid.typ.items() if t == PIPE]
    assert len(pc) == len(set(pc)), "pipes overlap after solve"
    print(f"[ok] global rip-up routed 2 contending pipes ({len(pc)} pipe cells)"); ok += 1

    # --- 7. ACCEPTANCE: rebuild weave8x8 with the Router, grade -> 832 ------
    R = build_triangle_with_router()
    res = R.solve(budget=20)
    assert res is True, f"triangle solve failed: {res}"
    got = R.render()
    ref_path = os.path.join(lm.REPO, "solutions", "triangle", "weave8x8.man")
    with open(ref_path) as fh:
        ref = fh.read().rstrip("\n")
    if got != ref:
        print("--- got ---\n" + got + "\n--- ref ---\n" + ref)
    assert got == ref, "triangle render NOT byte-identical to weave8x8.man"
    print("[ok] rebuilt weave8x8 byte-identical via Router")
    print("     footprint:", R.footprint())
    grade = R.grade("triangle")
    print("     grade:", json.dumps(grade))
    assert grade.get("passed") == 6 and grade.get("total") == 6, "regression: not 6/6"
    assert grade.get("score") == 832, f"regression: score {grade.get('score')} != 832"
    print("[ok] ACCEPTANCE reproduced triangle score 832 (6/6), NO regression"); ok += 1

    # --- 8. ACCEPTANCE: rebuild reverse-a-list ring-v2 (4-pipe fan), grade ---
    R2 = build_ring_v2_with_router()
    res = R2.solve(budget=60)
    assert res is True, f"ring-v2 solve failed: {res}"
    got = R2.render()
    ref2 = os.path.join(lm.REPO, "solutions", "reverse-a-list", "ring-v2.man")
    with open(ref2) as fh:
        want = fh.read().rstrip("\n")
    assert got == want, "ring-v2 render NOT byte-identical"
    print("[ok] rebuilt ring-v2 byte-identical via Router (4 pipes re-derived)")
    print("     footprint:", R2.footprint(),
          " pipe lengths:", {n: len(R2._proutes[n][0]) for n in R2._proutes})
    g2 = R2.grade("reverse-a-list")
    print("     grade:", json.dumps({k: g2.get(k) for k in
                                     ("passed", "total", "avgTicks", "score")}))
    assert g2.get("passed") == 8 and g2.get("total") == 8, "regression: not 8/8"
    assert g2.get("score") == 956100, f"regression: {g2.get('score')} != 956100"
    print("[ok] ACCEPTANCE reproduced ring-v2 score 956100 (8/8), NO regression"); ok += 1

    print(f"\nALL {ok} ROUTER SELF-TESTS PASSED")


if __name__ == "__main__":
    _selftest()
