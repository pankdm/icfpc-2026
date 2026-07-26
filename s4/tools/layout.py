"""layout.py — a LAYOUT-ASSIST layer for the littleman DSL.

The recurring bottleneck on the hard problems (plotter, matmul, sort, memory, …) is
turning a *validated* op-stream / flowchart into a **collision-free grid**: placing
men, instruction runs, turn glyphs and pipes without wall-hits, without two glyphs
landing on one cell, and while respecting littleman's pipe validity rules.

Every solution agent independently re-derived the same handful of helpers inside its
own ``solutions/<slug>/dsl.py``. This module UNIFIES the best of them into one tested,
reusable layer that sits ON TOP of ``tools/littleman.py`` (which it does not modify):

    from layout import Layout, place_pipe, route, relay_man, fifo_ring, auto_pipe

Consolidated from:
  * sort-numbers/dsl.py  — Placer (collision-checked put/vrun/hrun/corridor that
                           REFUSES to overwrite a differing glyph — catches the #1
                           hand-assembly bug), relay_man, ring_capacity.
  * memory/dsl.py        — Cur (walking cursor: emit/turn/goto).
  * brackets/dsl.py      — route (man-path through orthogonal waypoints).
  * triangle/dsl.py      — place_pipe (pipe that L-BENDS into the destination room).
  * reverse-a-list/dsl.py+stack_dsl.py — fifo_ring, pump/relay, pipelen, capacity.
  * plotter/dsl.py       — display-wiring geometry + the ADDR/DATA/SWAP ordering rule
                           (documented in fifo_ring / DISPLAY_ORDER below).

──────────────────────────────────────────────────────────────────────────────
WHAT THIS MODULE GIVES YOU
  1. Layout          — collision-checked placement + walking cursor in one object:
                       put / hrun / vrun / corridor / emit / turn / goto.
                       Raises Collision on overwriting a DIFFERING glyph; spaces are
                       free (writing a space never clobbers; a space is overwritable).
  2. place_pipe      — an L-bend pipe INTO a room (stock Program.pipe can only enter
                       straight-on and clobbers its last waypoint).
  3. route           — a MAN-path: turn glyphs at bends, straights left as nop spaces.
  4. relay_man /     — two-room FIFO storage (self-loop pipes are illegal, so a
     fifo_ring         circulating queue needs a second "relay" room), with the
                       ring_capacity / pipelen length helpers.
  5. auto_pipe       — a simple ORTHOGONAL AUTO-ROUTER (greedy border pick + BFS body)
                       that finds a VALID pipe between two room-border cells while
                       avoiding occupied cells. Enforces every oracle pipe rule below.

PIPE VALIDITY RULES (from docs/multi-man-interactions.md §4b/§6 + the pipe prose):
  * A pipe is a chain of >= 2 orthogonally-contiguous cells.
  * Arrowheads point WITH the flow, at the start, at every bend, and at the end;
    interior straight cells are body glyphs ('-' horizontal, '|' vertical).
  * The START cell's *backward* neighbour (start - flow_at_start) must sit on the
    SOURCE room's border.
  * The END cell's *forward* neighbour (end + flow_at_end) must sit on the
    DESTINATION room's border.
  * The arrowheads themselves must NOT land on a room border (leave >=1 clear cell of
    gap) — an arrow on a wall corrupts wall/room detection.
  * Pipes never carry men; a value only enters a room through the wall cell the
    arrowhead points at. With exactly one incoming and one outgoing pipe on a room,
    r/s are unambiguous (nearest-of-one) so the pipe may attach at ANY border cell.
──────────────────────────────────────────────────────────────────────────────
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import littleman as lm

# Re-export the core direction tables so callers need only import layout.
DIRS = dict(lm.DIRS)                 # {"E":(1,0), ...}
ARROW = dict(lm.ARROW)               # {"E":">", ...}
VEC2ARROW = dict(lm.VEC2ARROW)       # {(1,0):">", ...}

# The plotter's display wiring rule, kept here as documentation for reuse:
#   A 34x26 display has three incoming pipes — ADDR (top), DATA (left), SWAP (bottom).
#   Send ADDR_k before DATA_k for each pixel, and keep len(ADDR) <= len(DATA) <=
#   len(SWAP). Placing the compute room ABOVE the display makes ADDR a short vertical
#   drop, DATA route around to the left, SWAP around to the bottom — the lengths come
#   out ordered for free. (see solutions/plotter/dsl.py geometry()).
DISPLAY_ORDER = ("ADDR-top", "DATA-left", "SWAP-bottom")


class Collision(ValueError):
    """Raised when a placement would overwrite an existing DIFFERING glyph."""


def _unit(dx, dy):
    return ((dx > 0) - (dx < 0), (dy > 0) - (dy < 0))


# ──────────────────────────────────────────────────────────────────────────────
# 1. Layout — collision-checked placement API + walking cursor (Placer ∪ Cur)
# ──────────────────────────────────────────────────────────────────────────────
class Layout:
    """A collision-checking wrapper around a littleman ``Program`` that also carries a
    walking cursor. Every glyph goes through :meth:`put`, which turns "two glyphs
    collided on one cell" (an op landing on a corridor, a corridor crossing an op —
    the #1 hand-assembly bug) from a silent wrong answer into a loud ``Collision``.

    Truth is the underlying Program's cells, so glyphs drawn by ``program.room()`` /
    ``program.pipe()`` are protected too. SPACES ARE FREE: writing ``' '`` is a no-op
    that never clobbers, and any cell currently holding a space may be written over.
    Re-writing a cell with the SAME glyph is allowed (idempotent — handy for shared
    corridor/merge cells).

    Placement API (static):  put / hrun / vrun / corridor
    Cursor API   (walking):  goto / emit / turn
    """

    def __init__(self, program=None):
        self.p = program if program is not None else lm.Program()
        # cursor state
        self.cx = self.cy = 0
        self.cd = "E"

    # ---- collision-checked primitive ----
    def put(self, x, y, ch):
        """Place ``ch`` at (x,y). Space is free (no-op). Raise Collision on a differing
        non-space glyph. Returns self."""
        if ch == " ":
            return self                      # spaces are free — never clobber
        cur = self.p.get(x, y)
        if cur != " " and cur != ch:
            raise Collision(
                f"COLLISION at {(x, y)}: existing {cur!r} vs new {ch!r}")
        self.p.put(x, y, ch)
        return self

    def get(self, x, y):
        return self.p.get(x, y)

    # ---- static runs ----
    def hrun(self, x, y, s):
        """Place a horizontal (eastward) run of glyphs — e.g. a literal the man reads
        while walking east."""
        for i, c in enumerate(s):
            self.put(x + i, y, c)
        return self

    def vrun(self, x, y, s):
        """Place a vertical (southward) run of glyphs — e.g. a ``12345`` literal the
        man reads while walking south."""
        for i, c in enumerate(s):
            self.put(x, y + i, c)
        return self

    def corridor(self, a, b, turn_in, turn_out):
        """A straight space-corridor between axis-aligned endpoints ``a`` and ``b``.
        Only the two ENDPOINTS get turn glyphs; the interior is left untouched (free
        space) so other corridors may CROSS it safely (a space preserves heading; a
        corridor may never cross a foreign glyph). ``turn_in``/``turn_out`` are glyphs
        (e.g. 'v'/'<'). Build straight corridors this way — never a run of '>'/'<'
        fill — so crossings always land on spaces."""
        (x0, y0), (x1, y1) = a, b
        if x0 != x1 and y0 != y1:
            raise ValueError(f"corridor endpoints not axis-aligned: {a} {b}")
        self.put(x0, y0, turn_in)
        self.put(x1, y1, turn_out)
        return self

    # ---- walking cursor (Cur) ----
    def goto(self, x, y, d="E"):
        """Move the cursor to (x,y) heading ``d`` (E/W/N/S) without placing anything."""
        self.cx, self.cy, self.cd = x, y, d
        return self

    def emit(self, s):
        """Lay a run of instruction glyphs along the current heading, advancing the
        cursor one cell per glyph. Blank interior cells are no-op glides, so you place
        ONLY the instructions + turns; the man drifts straight through the gaps."""
        dx, dy = DIRS[self.cd]
        for ch in s:
            self.put(self.cx, self.cy, ch)
            self.cx += dx
            self.cy += dy
        return self

    def turn(self, nd):
        """Drop the arrow glyph for a new heading ``nd`` at the cursor, then step one
        cell into the new heading. (A room's '>'/'<'/'^'/'v' are ABSOLUTE direction
        sets, so a man arriving from any side leaves in that direction — which makes
        these arrows double as free MERGE points.)"""
        self.put(self.cx, self.cy, ARROW[nd])
        self.cd = nd
        dx, dy = DIRS[nd]
        self.cx += dx
        self.cy += dy
        return self

    # ---- convenience delegation to the Program (rooms drawn first, then protected) ----
    def room(self, *a, **k):
        return self.p.room(*a, **k)

    def input_room(self, *a, **k):
        return self.p.input_room(*a, **k)

    def output_room(self, *a, **k):
        return self.p.output_room(*a, **k)

    def display(self, *a, **k):
        return self.p.display(*a, **k)

    def man(self, x, y):
        """Place a man '@' (collision-checked)."""
        return self.put(x, y, "@")

    def pipe(self, points):
        """Delegate to Program.pipe (straight-on entry). For an L-bend into a room use
        :func:`place_pipe`; for auto-routing use :func:`auto_pipe`."""
        self.p.pipe(points)
        return self

    # ---- output / scoring passthrough ----
    def render(self):
        return self.p.render()

    def footprint(self):
        return self.p.footprint()

    def save(self, path):
        return self.p.save(path)

    def grade(self, slug):
        return self.p.grade(slug)


# small helper so pipe/route builders accept either a Program or a Layout
def _put(prog, x, y, ch):
    prog.put(x, y, ch)


# ──────────────────────────────────────────────────────────────────────────────
# 2. place_pipe — an L-bend pipe INTO a room
# ──────────────────────────────────────────────────────────────────────────────
def place_pipe(prog, path, exit_dir):
    """Draw a pipe over the explicit cell ``path`` (>=2 cells, source-adjacent first)
    that BENDS to enter the destination room from a perpendicular side.

    The stock ``Program.pipe`` derives the last cell's arrow from the previous segment
    (so it can only enter a room "straight on") AND writes an arrow onto its last
    waypoint (which must instead stay a free cell whose forward neighbour is the wall).
    ``place_pipe`` fixes both: the last cell is drawn as an arrowhead in ``exit_dir``,
    bending if needed.

    prog      : a Program or a Layout (pass a Layout for collision checking)
    path      : [(x,y), ...] the pipe's OWN cells; path[0]'s backward neighbour must be
                the source room border, path[-1] + exit_dir must be the dest border.
    exit_dir  : (dx,dy) the direction the value leaves path[-1] into the dest border.
    """
    n = len(path)
    if n < 2:
        raise ValueError("place_pipe: pipe needs >= 2 cells")
    dirs = [_unit(path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1])
            for i in range(n - 1)]
    dirs.append(tuple(exit_dir))                 # last cell bends toward the room
    for i, (cx, cy) in enumerate(path):
        di = dirs[i]
        bend = i > 0 and dirs[i - 1] != di
        if i == 0 or i == n - 1 or bend:
            _put(prog, cx, cy, VEC2ARROW[di])
        else:
            _put(prog, cx, cy, "-" if di[0] != 0 else "|")
    return prog


# ──────────────────────────────────────────────────────────────────────────────
# 3. route — a MAN-path (not a pipe) through orthogonal waypoints
# ──────────────────────────────────────────────────────────────────────────────
def route(prog, waypoints):
    """Lay a MAN-path through orthogonal ``waypoints``: place a turn arrow at each
    waypoint EXCEPT the last, and leave the straight cells between waypoints as free
    spaces (nops the man walks straight through). The final waypoint is the ARRIVAL
    cell — leave it as its target instruction (e.g. a '>' merge or an 'r').

    Because a man arriving at an arrow cell leaves in that ABSOLUTE direction, several
    routed branches can share a single '>' arrival cell as a free merge point.

    prog       : a Program or a Layout (pass a Layout for collision checking).
    waypoints  : [(x,y), ...] corner points; consecutive points must be axis-aligned.
    """
    for i in range(len(waypoints) - 1):
        (x0, y0), (x1, y1) = waypoints[i], waypoints[i + 1]
        if x0 != x1 and y0 != y1:
            raise ValueError(f"route segment not axis-aligned: {waypoints[i]} {waypoints[i+1]}")
        _put(prog, x0, y0, VEC2ARROW[_unit(x1 - x0, y1 - y0)])
    return prog


# ──────────────────────────────────────────────────────────────────────────────
# 4. FIFO storage — relay_man / fifo_ring + capacity/length helpers
# ──────────────────────────────────────────────────────────────────────────────
def pipelen(points):
    """Number of CELLS in a pipe routed through orthogonal waypoints ``points``."""
    n = 0
    for i in range(len(points) - 1):
        (x0, y0), (x1, y1) = points[i], points[i + 1]
        n += abs(x1 - x0) + abs(y1 - y0)
    return n + 1


def ring_capacity(feed_len, return_len):
    """Max values that can circulate in a two-pipe ring = feed_len + 1 (relay register)
    + return_len. Size the pipes so this is >= (max list length + 1 for a sentinel)."""
    return feed_len + 1 + return_len


def relay_man(prog, x, y, recv="R"):
    """Place a compact 2-row RELAY man that forever does ``<recv> ; s`` — receive a
    value, send it on — turning a CTRL→relay + relay→CTRL pipe pair into a single FIFO
    queue for the controller (``s`` enqueues, ``r`` dequeues). Self-loop pipes are
    illegal, so a circulating store ALWAYS needs this second room.

    Footprint: 4 wide x 2 tall with the man '@' at (x,y). The relay's room must have
    exactly ONE incoming and ONE outgoing pipe so ``recv``/``s`` are unambiguous.

    recv : 'R' (receive from ANY ready incoming pipe — robust default) or 'r' (nearest
           incoming pipe).  Racetrack:  @ > <recv> v  /  ^ s <
    """
    prog.put(x, y, "@")
    prog.put(x + 1, y, ">")
    prog.put(x + 2, y, recv)
    prog.put(x + 3, y, "v")
    prog.put(x + 1, y + 1, "^")
    prog.put(x + 2, y + 1, "s")
    prog.put(x + 3, y + 1, "<")
    return prog


def fifo_ring(prog, relay_rect, feed_pts, return_pts, recv="R"):
    """Build the RELAY half of a two-room FIFO ring: a relay room + relay man + the two
    pipes (FEED = controller→relay, RETURN = relay→controller). The controller room
    itself is the caller's; you pass the pipe waypoint lists that connect the two.

    prog        : a Program or a Layout.
    relay_rect  : (x, y, w, h) rectangle for the relay room (>= 5x4 to hold the man).
    feed_pts    : waypoints for the FEED pipe  (source=CTRL border → dest=relay border).
    return_pts  : waypoints for the RETURN pipe (source=relay border → dest=CTRL border).
    recv        : relay receive glyph ('R' or 'r').

    Returns a dict: {'capacity', 'feed_len', 'return_len', 'relay_rect'}.
    NOTE: the pipe waypoints and the controller's own r/s discipline are still the
    caller's responsibility (this is the still-manual part — see module notes). The
    ring must PHYSICALLY hold every value at once, so make
    ``ring_capacity(feed_len, return_len) >= n (+1 for a sentinel)``.
    """
    x, y, w, h = relay_rect
    if w < 5 or h < 4:
        raise ValueError("fifo_ring: relay room must be at least 5x4")
    prog.room(x, y, w, h) if hasattr(prog, "room") else lm.Program.room(prog, x, y, w, h)
    relay_man(prog, x + 1, y + 1, recv=recv)
    # draw the two pipes (straight-on entry via Program.pipe)
    (prog.p if isinstance(prog, Layout) else prog).pipe(list(feed_pts))
    (prog.p if isinstance(prog, Layout) else prog).pipe(list(return_pts))
    fl, rl = pipelen(feed_pts), pipelen(return_pts)
    return {"capacity": ring_capacity(fl, rl), "feed_len": fl,
            "return_len": rl, "relay_rect": relay_rect}


# ──────────────────────────────────────────────────────────────────────────────
# 5. auto_pipe — a simple ORTHOGONAL AUTO-ROUTER
# ──────────────────────────────────────────────────────────────────────────────
def _bfs(src, dst, blocked, bound):
    """Shortest orthogonal path of cells from src to dst avoiding ``blocked``.
    ``bound`` = (minx,miny,maxx,maxy) search box (inclusive). Returns [cells] or None."""
    from collections import deque
    minx, miny, maxx, maxy = bound
    if src == dst:
        return [src]
    seen = {src}
    q = deque([(src, [src])])
    while q:
        (cx, cy), path = q.popleft()
        for dx, dy in DIRS.values():
            nx, ny = cx + dx, cy + dy
            nc = (nx, ny)
            if nc in seen or not (minx <= nx <= maxx and miny <= ny <= maxy):
                continue
            if nc in blocked and nc != dst:
                continue
            if nc == dst:
                return path + [nc]
            seen.add(nc)
            q.append((nc, path + [nc]))
    return None


def auto_pipe(prog, src_border_pt, dst_border_pt, occupied=(), margin=4):
    """Auto-route a VALID pipe between two ROOM-BORDER cells, avoiding ``occupied``.

    ``src_border_pt`` and ``dst_border_pt`` are the WALL cells on the source and
    destination rooms. The router picks a first cell one step OUT of the source and a
    last cell one step OUT of the destination, then BFS-routes a body between them.
    The result satisfies every pipe rule (see module docstring):

      * >= 2 cells, orthogonally contiguous;
      * arrowheads point WITH the flow at start / bends / end;
      * start's backward neighbour == src_border_pt (flow leaves the source wall);
      * end's forward neighbour == dst_border_pt (flow enters the dest wall);
      * no pipe cell lands on ``occupied``, on either border point, or on a room wall
        already in ``prog``.

    prog       : a Program or a Layout (pass a Layout for collision checking).
    occupied   : iterable of (x,y) cells the pipe must avoid (walls, men, other pipes).
    margin     : how far outside the src/dst bounding box the router may wander.

    Returns the list of pipe cells (so the caller can add them to ``occupied``).
    Raises ValueError if no valid route is found. Greedy: prefers the border exits
    that head toward the other endpoint, then the shortest BFS body.
    """
    sb, db = tuple(src_border_pt), tuple(dst_border_pt)
    occ = set(map(tuple, occupied))
    # also treat any non-space cell already in prog as blocked (room walls, etc.)
    getter = prog.get if hasattr(prog, "get") else (lambda x, y: " ")

    xs = [sb[0], db[0]]
    ys = [sb[1], db[1]]
    bound = (min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin)

    def is_wall(c):
        return getter(c[0], c[1]) != " "

    def free(c):
        return c not in occ and c != sb and c != db and not is_wall(c)

    # order candidate exit directions by how much they reduce distance to the target
    def dirs_toward(frm, to):
        ds = list(DIRS.values())
        ds.sort(key=lambda d: abs(frm[0] + d[0] - to[0]) + abs(frm[1] + d[1] - to[1]))
        return ds

    best = None
    for out_dir in dirs_toward(sb, db):
        start = (sb[0] + out_dir[0], sb[1] + out_dir[1])
        if not free(start):
            continue
        for in_dir in dirs_toward(db, sb):
            # in_dir = flow direction ENTERING the dest wall; end sits one step back
            end = (db[0] - in_dir[0], db[1] - in_dir[1])
            if not free(end):
                continue
            # force straight stubs at both ends: BFS between the SECOND cell (start+out)
            # and the PENULTIMATE cell (end - in), so start's arrow == out_dir and
            # end's arrow == in_dir (the two border rules) with no bend on those cells.
            s2 = (start[0] + out_dir[0], start[1] + out_dir[1])
            e2 = (end[0] - in_dir[0], end[1] - in_dir[1])
            # assemble the mandatory prefix/suffix and the BFS middle
            prefix, suffix = [start], [end]
            a, b = start, end
            if s2 != start and s2 != end and free(s2):
                prefix = [start, s2]
                a = s2
            if e2 != end and e2 != start and e2 != s2 and free(e2):
                suffix = [e2, end]
                b = e2
            blocked = occ | {sb, db} | {c for c in prefix + suffix}
            mid = _bfs(a, b, blocked, bound)
            if mid is None:
                continue
            # stitch: prefix (minus its last, which is `a`) + mid + suffix (minus first `b`)
            path = prefix[:-1] + mid + suffix[1:]
            # dedupe accidental repeats & verify contiguity/validity
            if len(path) < 2:
                continue
            if best is None or len(path) < len(best[0]):
                best = (path, out_dir, in_dir)
        # greedy: accept the first out_dir that yielded any route (already shortest over in_dir)
        if best is not None:
            break

    if best is None:
        raise ValueError(
            f"auto_pipe: no valid route from {sb} to {db} avoiding {len(occ)} cells")

    path, out_dir, in_dir = best
    # draw arrowheads with-flow: dirs[0]=out_dir, interior=segment dirs, dirs[-1]=in_dir
    n = len(path)
    dirs = [out_dir]
    for i in range(1, n):
        dirs.append(_unit(path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1]))
    dirs[-1] = in_dir
    for i, (cx, cy) in enumerate(path):
        di = dirs[i]
        bend = 0 < i < n - 1 and dirs[i - 1] != di
        if i == 0 or i == n - 1 or bend:
            _put(prog, cx, cy, VEC2ARROW[di])
        else:
            _put(prog, cx, cy, "-" if di[0] != 0 else "|")
    return path


# ──────────────────────────────────────────────────────────────────────────────
# VALIDATION HELPERS (used by the self-test below)
# ──────────────────────────────────────────────────────────────────────────────
def validate_pipe(path, src_border_pt, dst_border_pt, occupied=()):
    """Assert ``path`` obeys the pipe validity rules. Raises AssertionError otherwise."""
    sb, db, occ = tuple(src_border_pt), tuple(dst_border_pt), set(map(tuple, occupied))
    assert len(path) >= 2, "pipe must have >= 2 cells"
    for i in range(1, len(path)):
        dx = abs(path[i][0] - path[i - 1][0]) + abs(path[i][1] - path[i - 1][1])
        assert dx == 1, f"pipe cells not contiguous at {path[i-1]}->{path[i]}"
    assert len(set(path)) == len(path), "pipe self-intersects"
    for c in path:
        assert c not in occ, f"pipe crosses occupied cell {c}"
        assert c != sb and c != db, "pipe overlaps a border point"
    f0 = _unit(path[1][0] - path[0][0], path[1][1] - path[0][1])
    back = (path[0][0] - f0[0], path[0][1] - f0[1])
    assert back == sb, f"start backward neighbour {back} != src border {sb}"
    fl = _unit(path[-1][0] - path[-2][0], path[-1][1] - path[-2][1])
    fwd = (path[-1][0] + fl[0], path[-1][1] + fl[1])
    assert fwd == db, f"end forward neighbour {fwd} != dst border {db}"
    return True


# ──────────────────────────────────────────────────────────────────────────────
# DEMO / SELF-TEST
# ──────────────────────────────────────────────────────────────────────────────
def build_triangle_weave():
    """Reconstruct solutions/triangle/weave8x8.man using ONLY layout.py + littleman.py.

    An 8x4 compute room; a single man walks EAST computing n(n+1) = @ r M * + , turns
    SOUTH then WEST, then walks WEST doing W 2 W / s (=> /2, send). Two L-bend pipes:
    input I→compute (bends NORTH) and output compute→O (bends WEST).
    Known-good score: 6/6, footprint 8x8 (box 64), avgTicks 13, score 832.
    """
    L = Layout()
    L.room(0, 0, 8, 4)                       # compute room, interior cols 1-6 rows 1-2
    L.input_room(0, 4)                       # I room below-left (I at 1,5)
    L.output_room(3, 5)                      # O room below-right (O at 4,6)

    # the walking man: east along row 1, bend south, bend west, west along row 2
    L.goto(1, 1, "E").emit("@rM*+").turn("S").turn("W").emit("W2W/s")

    # input pipe: I border (2,4) -> cell (3,4) east -> cell (4,4) bends NORTH into compute
    place_pipe(L, [(3, 4), (4, 4)], exit_dir=DIRS["N"])
    # output pipe: compute border (6,3) -> cell (6,4) south -> cell (6,5) bends WEST into O
    place_pipe(L, [(6, 4), (6, 5)], exit_dir=DIRS["W"])
    return L


def _selftest():
    import json
    ok = 0

    # --- 1. Layout collision semantics -------------------------------------
    L = Layout()
    L.put(0, 0, "a")
    L.put(0, 0, "a")                         # same glyph: idempotent, no raise
    L.put(0, 0, " ")                         # space is free: no clobber
    assert L.get(0, 0) == "a"
    try:
        L.put(0, 0, "b")                     # differing glyph: must raise
        raise SystemExit("FAIL: collision not detected")
    except Collision:
        pass
    L.hrun(0, 2, "xyz"); assert L.get(2, 2) == "z"
    L.vrun(5, 0, "pq"); assert L.get(5, 1) == "q"
    L.goto(0, 5, "E").emit("ab").turn("S").emit("cd")
    assert L.get(0, 5) == "a" and L.get(2, 5) == "v" and L.get(2, 7) == "d"
    print("[ok] Layout put/hrun/vrun/emit/turn/collision"); ok += 1

    # --- 2. route (man-path): arrows at bends, spaces between --------------
    Lr = Layout()
    route(Lr, [(0, 0), (3, 0), (3, 2)])
    assert Lr.get(0, 0) == ">" and Lr.get(3, 0) == "v" and Lr.get(1, 0) == " "
    print("[ok] route man-path (turn glyphs at bends, spaces between)"); ok += 1

    # --- 3. place_pipe reproduces the weave's two L-bend pipes -------------
    Lp = Layout()
    place_pipe(Lp, [(3, 4), (4, 4)], DIRS["N"])
    assert Lp.get(3, 4) == ">" and Lp.get(4, 4) == "^"
    place_pipe(Lp, [(6, 4), (6, 5)], DIRS["W"])
    assert Lp.get(6, 4) == "v" and Lp.get(6, 5) == "<"
    print("[ok] place_pipe L-bend into room"); ok += 1

    # --- 4. fifo_ring + capacity/length helpers ----------------------------
    assert pipelen([(0, 0), (0, 3), (2, 3)]) == 6
    assert ring_capacity(5, 5) == 11
    Lf = Layout()
    Lf.room(0, 0, 10, 5)                                  # controller
    info = fifo_ring(Lf, (0, 8, 6, 4),
                     feed_pts=[(3, 5), (3, 7)],           # ctrl bottom -> relay top
                     return_pts=[(6, 9), (8, 9), (8, 5)]) # relay right -> ctrl bottom
    assert info["capacity"] == ring_capacity(info["feed_len"], info["return_len"])
    assert Lf.get(1, 9) == "@"                            # relay man placed
    print(f"[ok] fifo_ring built, capacity={info['capacity']}"); ok += 1

    # --- 5. auto_pipe: valid orthogonal route around obstacles -------------
    # source wall at (2,2), dest wall at (10,2), a blocking column at x=6.
    La = Layout()
    occ = {(6, y) for y in range(0, 3)}
    p_a = auto_pipe(La, (2, 2), (10, 2), occupied=occ)
    validate_pipe(p_a, (2, 2), (10, 2), occupied=occ)
    assert len(p_a) >= 2
    # a straight run with no obstacles
    Lb = Layout()
    p_b = auto_pipe(Lb, (0, 0), (0, 5), occupied=())
    validate_pipe(p_b, (0, 0), (0, 5))
    print(f"[ok] auto_pipe routed ({len(p_a)} cells around obstacle, {len(p_b)} straight)"); ok += 1

    # --- 6. VALIDATION: rebuild weave8x8 with layout.py only, grade it -----
    L8 = build_triangle_weave()
    got = L8.render()
    ref_path = os.path.join(lm.REPO, "solutions", "triangle", "weave8x8.man")
    with open(ref_path) as fh:
        ref = fh.read().rstrip("\n")
    assert got == ref, f"render mismatch:\n--- got ---\n{got}\n--- ref ---\n{ref}"
    print("[ok] rebuilt weave8x8 byte-identical to solutions/triangle/weave8x8.man")
    print("     footprint:", L8.footprint())
    g = L8.grade("triangle")
    print("     grade:", json.dumps(g))
    assert g.get("passed") == 6 and g.get("total") == 6, "regression: not 6/6"
    assert g.get("score") == 832, f"regression: score {g.get('score')} != 832"
    print("[ok] reproduced known score 832 (6/6), NO regression"); ok += 1

    print(f"\nALL {ok} SELF-TESTS PASSED")


if __name__ == "__main__":
    _selftest()
