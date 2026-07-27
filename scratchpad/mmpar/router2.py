"""router2 — A* pipe router with a HARD 1-cell halo and TARGETED rip-up/reroute.

Three facts force this design (all measured while building the P=2 engine):
  * two pipes laid side by side parse as ONE pipe (a gapless serpentine is a
    single pipe by design), so every pipe needs a 1-cell exclusion halo;
  * with the halo, greedy shortest-path search walls the canvas off after a few
    nets and NO ordering of 11 nets ever routed (400 random orders tried);
  * random rip-up never converges either (1300 steps, 17/28 nets still pending).

What works is PathFinder-style TARGETED rip-up: when a net cannot route, re-run
the search with other nets' cells passable at a penalty, then evict exactly the
nets on that soft path and route through the hole they leave.
"""
import heapq
from collections import deque

from mm2lib import DIRS, VEC2ARROW

STEPS = ((1, 0), (-1, 0), (0, 1), (0, -1))
SOFT = 40.0          # penalty per occupied cell in the soft (rip-up planning) pass


class Canvas:
    def __init__(self, g, rects, bound):
        self.g = g
        self.bound = bound
        self.h = {}                      # halo cell -> list of owner ids
        self.cown = {}                   # pipe cell  -> owner id
        self.owner = {}                  # net id -> (cells, halo cells)
        self.hist = {}                   # PathFinder history cost per cell
        for (x, y, w, hh) in rects:
            for i in range(x + 1, x + w - 1):
                for j in range(y + 1, y + hh - 1):
                    if g.get(i, j) == ' ':
                        g.put(i, j, '\x01')
            border = ([(x + i, y) for i in range(w)] +
                      [(x + i, y + hh - 1) for i in range(w)] +
                      [(x, y + j) for j in range(hh)] +
                      [(x + w - 1, y + j) for j in range(hh)])
            self.add_halo(border, None)

    def add_halo(self, cells, owner):
        got = []
        for (x, y) in cells:
            for dx, dy in STEPS:
                c = (x + dx, y + dy)
                self.h.setdefault(c, []).append(owner)
                got.append(c)
        if owner is not None:
            for c in cells:
                self.cown[c] = owner
        return got

    def _drop_halo(self, cells, owner):
        for c in cells:
            lst = self.h.get(c)
            if lst:
                lst.remove(owner)
                if not lst:
                    del self.h[c]

    def blockers(self, c):
        out = []
        if self.g.get(*c) != ' ':
            out.append(self.cown.get(c))          # None => room / permanent
        out.extend(self.h.get(c, ()))
        return out

    def _search(self, src_att, src_dir, dst_att, margin, soft):
        exempt = {src_att, dst_att}
        for c in (src_att, dst_att):
            for dx, dy in STEPS:
                exempt.add((c[0] + dx, c[1] + dy))
        d = DIRS[src_dir]
        s2 = (src_att[0] + d[0], src_att[1] + d[1])
        bx0, by0, bx1, by1 = self.bound
        x0 = max(bx0, min(src_att[0], dst_att[0]) - margin)
        x1 = min(bx1, max(src_att[0], dst_att[0]) + margin)
        y0 = max(by0, min(src_att[1], dst_att[1]) - margin)
        y1 = min(by1, max(src_att[1], dst_att[1]) + margin)
        gx, gy = dst_att

        def cell_cost(c):
            if c in exempt:
                return 0.0
            bl = self.blockers(c)
            if not bl:
                return 0.0
            if not soft or None in bl:
                return None
            return SOFT * len(bl)

        def step_cost(c):
            return 1.0 + self.hist.get(c, 0.0)

        if cell_cost(s2) is None:
            return None
        prev = {s2: None}
        best = {s2: 0.0}
        heap = [(abs(s2[0] - gx) + abs(s2[1] - gy), 0.0, s2)]
        while heap:
            _, dcost, c = heapq.heappop(heap)
            if dcost > best.get(c, 1e18) + 1e-9:
                continue
            if c == dst_att:
                path = []
                while c is not None:
                    path.append(c)
                    c = prev[c]
                return path[::-1]
            for dx, dy in STEPS:
                n = (c[0] + dx, c[1] + dy)
                if not (x0 <= n[0] <= x1 and y0 <= n[1] <= y1):
                    continue
                extra = 0.0 if n == dst_att else cell_cost(n)
                if extra is None:
                    continue
                nd = dcost + step_cost(n) + extra
                if nd < best.get(n, 1e18) - 1e-9:
                    best[n] = nd
                    prev[n] = c
                    heapq.heappush(heap, (nd + abs(n[0] - gx) + abs(n[1] - gy),
                                          nd, n))
        return None

    def route(self, nid, src_att, src_dir, dst_att, dst_dir, margin=60):
        p = self._search(src_att, src_dir, dst_att, margin, soft=False)
        if p is None:
            return None
        cells = [src_att] + p
        self._draw(cells, dst_dir)
        halo = self.add_halo(cells, nid)
        self.owner[nid] = (cells, halo)
        return cells

    def plan_ripup(self, src_att, src_dir, dst_att, margin=60):
        p = self._search(src_att, src_dir, dst_att, margin, soft=True)
        if p is None:
            return None
        vic = set()
        for c in p:
            bl = self.blockers(c)
            if bl:
                self.hist[c] = self.hist.get(c, 0.0) + 1.5
            for o in bl:
                if o is not None:
                    vic.add(o)
        return vic

    def _draw(self, cells, end_direction):
        dirs = []
        for i in range(len(cells)):
            if i < len(cells) - 1:
                dirs.append((cells[i + 1][0] - cells[i][0],
                             cells[i + 1][1] - cells[i][1]))
            else:
                dirs.append(DIRS[end_direction])
        for i, (x, y) in enumerate(cells):
            bend = i > 0 and dirs[i - 1] != dirs[i]
            dx, dy = dirs[i]
            ch = (VEC2ARROW[(dx, dy)] if (i == 0 or i == len(cells) - 1 or bend)
                  else ('-' if dx else '|'))
            self.g.put(x, y, ch, force=True)

    def rip(self, nid):
        cells, halo = self.owner.pop(nid)
        for c in cells:
            self.g.c.pop(c, None)
            self.cown.pop(c, None)
        self._drop_halo(halo, nid)


def wire_all(g, rects, nets, bound, budget=3000, verbose=False, prewired=(),
             margin=60):
    cv = Canvas(g, rects, bound)
    for cells in prewired:
        cv.add_halo(cells, None)
        for c in cells:
            cv.cown[c] = None
    for (sa, sd, da, dd) in nets:
        for c in (sa, da):
            if g.get(*c) == '\x01':
                g.c.pop(c, None)
    pending = deque(sorted(range(len(nets)),
                           key=lambda i: -(abs(nets[i][0][0] - nets[i][2][0]) +
                                           abs(nets[i][0][1] - nets[i][2][1]))))
    steps = 0
    while pending:
        steps += 1
        if steps > budget:
            raise ValueError(f"router2: budget exhausted, {len(pending)} left "
                             f"{list(pending)}")
        i = pending.popleft()
        sa, sd, da, dd = nets[i]
        if cv.route(i, sa, sd, da, dd, margin) is not None:
            continue
        vic = cv.plan_ripup(sa, sd, da, margin)
        if not vic:
            raise ValueError(f"router2: net {i} {sa}->{da} unroutable even with "
                             f"every other net removed (permanent blocker)")
        for j in vic:
            cv.rip(j)
            pending.append(j)
        pending.appendleft(i)
        if verbose:
            print(f"  step {steps}: net {i} ripped {sorted(vic)}, "
                  f"pending {len(pending)}", flush=True)
    if verbose:
        print(f"  routed all {len(nets)} nets in {steps} steps", flush=True)
    return cv


# ═══════════════════════════════════════════════════════════════════════════
# PathFinder negotiated-congestion router.  Targeted rip-up (above) gets to
# ~9/28 nets pending and then cycles forever; this one lets nets OVERLAP at an
# escalating price until they negotiate a legal solution.
# ═══════════════════════════════════════════════════════════════════════════
class PFCanvas:
    def __init__(self, g, rects, bound, blocked_cells=()):
        self.g = g
        self.bound = bound
        self.hard = set()                # rooms + prewired pipes + their halos
        self.occ = {}                    # cell -> list of net ids
        self.hist = {}
        self.foot = {}                   # net id -> set of cells
        for (x, y, w, hh) in rects:
            for i in range(x, x + w):
                for j in range(y, y + hh):
                    self.hard.add((i, j))
            for i in range(x - 1, x + w + 1):
                for j in range(y - 1, y + hh + 1):
                    self.hard.add((i, j))
        for c in blocked_cells:
            self.hard.add(c)
            for dx, dy in STEPS:
                self.hard.add((c[0] + dx, c[1] + dy))

    def _cost(self, c, pres):
        n = len(self.occ.get(c, ()))
        return (1.0 + self.hist.get(c, 0.0)) * (1.0 + pres * n)

    def search(self, src_att, src_dir, dst_att, pres):
        exempt = {src_att, dst_att}
        for c in (src_att, dst_att):
            for dx, dy in STEPS:
                exempt.add((c[0] + dx, c[1] + dy))
        d = DIRS[src_dir]
        s2 = (src_att[0] + d[0], src_att[1] + d[1])
        x0, y0, x1, y1 = self.bound
        gx, gy = dst_att
        if s2 in self.hard and s2 not in exempt:
            return None
        prev = {s2: None}
        best = {s2: 0.0}
        heap = [(0.0, 0.0, s2)]
        while heap:
            _, dc, c = heapq.heappop(heap)
            if dc > best.get(c, 1e18) + 1e-9:
                continue
            if c == dst_att:
                path = []
                while c is not None:
                    path.append(c)
                    c = prev[c]
                return path[::-1]
            for dx, dy in STEPS:
                n = (c[0] + dx, c[1] + dy)
                if not (x0 <= n[0] <= x1 and y0 <= n[1] <= y1):
                    continue
                if n in self.hard and n not in exempt:
                    continue
                nd = dc + (0.0 if n in exempt else self._cost(n, pres))
                if nd < best.get(n, 1e18) - 1e-9:
                    best[n] = nd
                    prev[n] = c
                    heapq.heappush(heap, (nd + abs(n[0] - gx) + abs(n[1] - gy),
                                          nd, n))
        return None

    def add(self, nid, cells):
        f = set(cells)
        for (x, y) in cells:
            for dx, dy in STEPS:
                f.add((x + dx, y + dy))
        self.foot[nid] = f
        for c in f:
            self.occ.setdefault(c, []).append(nid)

    def remove(self, nid):
        for c in self.foot.pop(nid, ()):
            self.occ[c].remove(nid)
            if not self.occ[c]:
                del self.occ[c]


def pathfinder(g, rects, nets, bound, prewired=(), iters=80, verbose=False):
    blocked = [c for cells in prewired for c in cells]
    cv = PFCanvas(g, rects, bound, blocked)
    for (sa, sd, da, dd) in nets:
        for c in (sa, da):
            cv.hard.discard(c)
            for dx, dy in STEPS:
                cv.hard.discard((c[0] + dx, c[1] + dy))
    for (x, y, w, hh) in rects:                 # rooms themselves stay hard
        for i in range(x, x + w):
            for j in range(y, y + hh):
                cv.hard.add((i, j))
    for cells in prewired:
        for c in cells:
            cv.hard.add(c)
    routes = {}
    pres = 0.6
    for it in range(iters):
        for i, (sa, sd, da, dd) in enumerate(nets):
            if i in routes:
                cv.remove(i)
            p = cv.search(sa, sd, da, pres)
            if p is None:
                raise ValueError(f"pathfinder: net {i} {sa}->{da} has no path at all")
            routes[i] = [sa] + p
            cv.add(i, routes[i])
        if verbose and it == 0:
            print('   lens', [len(routes[i]) for i in range(len(nets))], flush=True)
        bad = [c for c, o in cv.occ.items() if len(o) > 1]
        if verbose:
            print(f"  iter {it}: {len(bad)} contended cells, pres={pres:.2f}",
                  flush=True)
        if not bad:
            for i, (sa, sd, da, dd) in enumerate(nets):
                _draw_cells(g, routes[i], dd)
            return routes
        for c in bad:
            cv.hist[c] = cv.hist.get(c, 0.0) + 0.6
        pres *= 1.6
    raise ValueError(f"pathfinder: {len(bad)} contended cells after {iters} iters")


def _draw_cells(g, cells, end_direction):
    dirs = []
    for i in range(len(cells)):
        if i < len(cells) - 1:
            dirs.append((cells[i + 1][0] - cells[i][0],
                         cells[i + 1][1] - cells[i][1]))
        else:
            dirs.append(DIRS[end_direction])
    for i, (x, y) in enumerate(cells):
        bend = i > 0 and dirs[i - 1] != dirs[i]
        dx, dy = dirs[i]
        ch = (VEC2ARROW[(dx, dy)] if (i == 0 or i == len(cells) - 1 or bend)
              else ('-' if dx else '|'))
        g.put(x, y, ch, force=True)
